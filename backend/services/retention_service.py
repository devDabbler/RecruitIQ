"""Candidate data retention (pilot plan Track 1 #6).

A candidate whose record has seen no activity for RETENTION_DAYS is erased
completely, through the same erasure_service path an admin's delete uses, so
retention can never leave behind something a manual delete would remove.

"Activity" is the newest timestamp on any row erasure would remove: the
profile itself, applications and their stage history, interviews, feedback,
emails sent, notes, tags, saved jobs, pitches, resumes. Reading a record is
not activity (views live in the audit log, which is deliberately left out).

Two kinds of candidate are held rather than erased, and counted in the report
so an admin can act on them:

- anyone with an application still in progress (not hired, rejected,
  declined or withdrawn): a live process is never cut short by a timer;
- anyone with no timestamp at all (legacy rows), since their age is unknown.

Each erasure is recorded in audit_events as a `delete` by the `system` actor,
so the log shows who removed a record even when nobody did it by hand.

ACTIVITY_COLUMNS must name every table in erasure_service.ERASED_TABLES (a
test enforces it), so a new table holding candidate data forces a decision
about whether its rows count as activity.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.models import AuditEvent
from backend.services import erasure_service
from backend.services.pipeline_service import TERMINAL

logger = logging.getLogger(__name__)

# Shortest window the job accepts. A typo such as RETENTION_DAYS=3 would
# otherwise erase every candidate who went quiet last week.
MIN_RETENTION_DAYS = 30

AUDIT_ENDPOINT = "retention job"

# Timestamp columns that mark activity, per table erasure removes.
ACTIVITY_COLUMNS: dict[str, tuple[str, ...]] = {
    "candidates": ("created_at", "updated_at"),
    "job_applications": ("applied_at", "updated_at"),
    "application_stages": ("started_at", "completed_at"),
    "interviews": ("created_at",),
    "feedback": ("submitted_at", "updated_at"),
    "email_log": ("created_at",),
    "notes": ("created_at",),
    "candidate_tags": ("created_at",),
    "saved_jobs": ("saved_at",),
    "candidate_pitches": ("created_at", "updated_at"),
    "candidate_skills": ("created_at", "updated_at"),
    "candidate_education": ("created_at", "updated_at"),
    "candidate_experience": ("created_at", "updated_at"),
    "resumes": ("created_at", "updated_at"),
}

HELD_OPEN_APPLICATION = "open application"
HELD_UNDATED = "no recorded activity date"


class RetentionConfigError(ValueError):
    pass


@dataclass
class InactiveCandidate:
    candidate_id: str
    last_activity: Optional[datetime]
    held: Optional[str] = None


@dataclass
class RetentionReport:
    days: int
    cutoff: datetime
    dry_run: bool
    expired: list[InactiveCandidate] = field(default_factory=list)
    held: list[InactiveCandidate] = field(default_factory=list)
    erased: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def summary(self) -> str:
        held_by_reason: dict[str, int] = {}
        for c in self.held:
            held_by_reason[c.held or ""] = held_by_reason.get(c.held or "", 0) + 1
        held = ", ".join(f"{n} {reason}" for reason, n in sorted(held_by_reason.items())) or "none"
        verb = "would erase" if self.dry_run else "erased"
        done = len(self.expired) if self.dry_run else len(self.erased)
        return (
            f"retention {self.days}d (inactive since before {self.cutoff:%Y-%m-%d}): "
            f"{verb} {done}, held {len(self.held)} ({held}), failed {len(self.failed)}"
        )


def check_days(days: int) -> int:
    if days < MIN_RETENTION_DAYS:
        raise RetentionConfigError(
            f"retention window must be at least {MIN_RETENTION_DAYS} days, got {days}"
        )
    return days


def _last_activity_sql() -> str:
    where_by_table = dict(erasure_service.ERASURE_STEPS)
    parts = []
    for table, columns in ACTIVITY_COLUMNS.items():
        if not columns:
            continue
        newest = columns[0] if len(columns) == 1 else f"GREATEST({', '.join(columns)})"
        where = where_by_table[table].replace(":cid", "c.id")
        parts.append(f"(SELECT MAX({newest}) FROM {table} WHERE {where})")
    return f"GREATEST({', '.join(parts)})"


def find_inactive(db: Session, cutoff: datetime) -> tuple[list[InactiveCandidate], list[InactiveCandidate]]:
    """Candidates with no activity since `cutoff`: (to erase, held back)."""
    terminal = ", ".join(f"'{status}'" for status in sorted(TERMINAL))
    rows = db.execute(
        text(
            f"SELECT id, last_activity, open_application FROM ("
            f"  SELECT c.id, {_last_activity_sql()} AS last_activity,"
            f"    EXISTS (SELECT 1 FROM job_applications a WHERE a.candidate_id = c.id"
            f"            AND COALESCE(a.status, '') NOT IN ({terminal})) AS open_application"
            f"  FROM candidates c"
            f") t WHERE last_activity IS NULL OR last_activity < :cutoff "
            f"ORDER BY last_activity NULLS FIRST, id"
        ),
        {"cutoff": cutoff},
    ).all()

    expired: list[InactiveCandidate] = []
    held: list[InactiveCandidate] = []
    for row in rows:
        candidate = InactiveCandidate(candidate_id=row.id, last_activity=row.last_activity)
        if row.last_activity is None:
            candidate.held = HELD_UNDATED
        elif row.open_application:
            candidate.held = HELD_OPEN_APPLICATION
        (held if candidate.held else expired).append(candidate)
    return expired, held


def run_retention(
    db: Session,
    days: int,
    *,
    dry_run: bool = False,
    now: Optional[datetime] = None,
    storage: Optional[Any] = None,
    redis_client: Optional[Any] = None,
) -> RetentionReport:
    """Erase every candidate inactive for `days` days; report what happened.

    Each candidate is erased and audited in its own transaction, so one
    failure is logged and counted without undoing or blocking the rest.
    """
    check_days(days)
    cutoff = (now or datetime.utcnow()) - timedelta(days=days)
    expired, held = find_inactive(db, cutoff)
    report = RetentionReport(days=days, cutoff=cutoff, dry_run=dry_run, expired=expired, held=held)
    if dry_run:
        return report

    for candidate in expired:
        cid = candidate.candidate_id
        try:
            erasure_service.erase_candidate(db, cid, storage=storage, redis_client=redis_client)
        except erasure_service.CandidateNotFound:
            continue  # erased by someone else since the scan; nothing left to do
        except Exception as exc:
            report.failed.append(cid)
            logger.error("Retention: erasure of candidate %s failed: %s", cid, exc)
            continue
        report.erased.append(cid)
        try:
            db.add(
                AuditEvent(
                    actor_id=None,
                    actor_role="system",
                    action="delete",
                    subject_type="candidate",
                    subject_id=cid,
                    candidate_id=cid,
                    endpoint=AUDIT_ENDPOINT,
                    detail=f"retention {days}d",
                    status_code=200,
                )
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Retention: candidate %s erased but the audit row failed: %s", cid, exc)
    return report
