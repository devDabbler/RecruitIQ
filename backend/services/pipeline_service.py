"""Every pipeline transition lives here (ATS Phase A, spec 2026-10-03 section 4).

Routers call these and nothing else touches `application_stages` or
`candidates.status`. The functions mutate the session but do not commit, so a
router can compose several and commit once; the tests run inside the
rolled-back fixture transaction the same way.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.models import ApplicationStage, Candidate, JobApplication, PipelineStage

# (key, name, kind, description). Canonical names from the spec, section 4.
DEFAULT_STAGES: list[tuple[str, str, str, str]] = [
    ("resume_submitted", "Resume submitted", "round", "We have your resume and are reviewing it."),
    ("hm_review", "Hiring manager review", "round", "The hiring manager reviews your background against the role."),
    ("technical_written", "Technical assessment", "round", "A take-home or written exercise on the fundamentals of the role."),
    ("technical_interview", "Technical interview", "round", "A live conversation going deep on your primary area."),
    ("problem_solving", "Problem solving", "round", "An open-ended reasoning session with the team."),
    ("case_study", "Case study", "round", "A scenario-based discussion with a small panel."),
    ("hr_screen", "HR screen", "round", "A final conversation about logistics, timing, and references."),
    ("offer", "Offer", "round", "An offer has been extended."),
    ("offer_accepted", "Offer accepted", "round", "You have accepted. We are completing paperwork and a start date."),
    ("offer_declined", "Offer declined", "outcome", "You declined the offer."),
    ("hired", "Hired", "outcome", "Welcome aboard."),
]

ROUND = "round"
OUTCOME = "outcome"

PENDING = "pending"
IN_PROGRESS = "in_progress"
PASSED = "passed"
FAILED = "failed"
SKIPPED = "skipped"

APP_ACTIVE = "active"
APP_HIRED = "hired"
APP_REJECTED = "rejected"
APP_DECLINED = "declined"
APP_WITHDRAWN = "withdrawn"
TERMINAL = frozenset({APP_HIRED, APP_REJECTED, APP_DECLINED, APP_WITHDRAWN})

DECLINABLE_KEYS = frozenset({"offer", "offer_accepted"})

# Stage key -> candidates.status (spec section 3.3).
_STAGE_TO_CANDIDATE_STATUS = {
    "resume_submitted": "active",
    "hm_review": "screening",
    "technical_written": "interviewing",
    "technical_interview": "interviewing",
    "problem_solving": "interviewing",
    "case_study": "interviewing",
    "hr_screen": "interviewing",
    "offer": "offered",
    "offer_accepted": "offered",
}
_APP_TO_CANDIDATE_STATUS = {
    APP_HIRED: "hired",
    APP_REJECTED: "rejected",
    APP_DECLINED: "withdrawn",
    APP_WITHDRAWN: "withdrawn",
}


class PipelineError(Exception):
    """A transition that is not allowed from the application's current state."""


def ensure_job_stages(db: Session, job_id: int) -> list[PipelineStage]:
    """The job's stages in order, creating the defaults the first time."""
    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.job_id == job_id)
        .order_by(PipelineStage.position)
        .all()
    )
    if stages:
        return stages
    for position, (key, name, kind, description) in enumerate(DEFAULT_STAGES, start=1):
        db.add(
            PipelineStage(
                job_id=job_id,
                key=key,
                name=name,
                kind=kind,
                description=description,
                position=position,
                enabled=True,
            )
        )
    db.flush()
    return (
        db.query(PipelineStage)
        .filter(PipelineStage.job_id == job_id)
        .order_by(PipelineStage.position)
        .all()
    )


def ensure_application_stages(db: Session, application: JobApplication) -> list[ApplicationStage]:
    """The application's stage rows in pipeline order, creating them if absent.

    Absent rows mean an application that predates Phase A and was not reached
    by the migration (a fresh row inserted by old code, or a test fixture). It
    starts at the first enabled round, like a new application would.
    """
    stages = ensure_job_stages(db, application.job_id)
    existing = {row.stage_id: row for row in application.stages}
    if len(existing) == len(stages):
        return _ordered(application)

    now = datetime.utcnow()
    started = any(row.status != PENDING for row in existing.values())
    entered: Optional[ApplicationStage] = None
    for stage in stages:
        if stage.id in existing:
            continue
        row = ApplicationStage(application_id=application.id, stage_id=stage.id, status=PENDING)
        if not started and stage.kind == ROUND and stage.enabled:
            row.status = IN_PROGRESS
            row.started_at = application.applied_at or now
            started = True
            entered = row
        db.add(row)
    db.flush()
    if entered is not None:
        on_stage_entered(db, entered)
    db.refresh(application)
    if application.status not in TERMINAL:
        application.status = APP_ACTIVE
    sync_candidate_status(db, application)
    return _ordered(application)


def on_stage_entered(db: Session, row: ApplicationStage) -> None:
    """Runs whenever an application starts a round (ATS Phase B: default interviewers)."""
    if row.application.status in TERMINAL:
        return
    # Imported here: feedback_service imports this module.
    from backend.services import feedback_service

    feedback_service.apply_default_interviewers(db, row)


def start_application(db: Session, application: JobApplication) -> list[ApplicationStage]:
    """A brand-new application: stage 1 in progress, candidate status synced."""
    application.status = APP_ACTIVE
    db.flush()
    return ensure_application_stages(db, application)


def current_stage(application: JobApplication) -> Optional[ApplicationStage]:
    for row in application.stages:
        if row.status == IN_PROGRESS:
            return row
    return None


def sync_candidate_status(db: Session, application: JobApplication) -> None:
    """Recompute candidates.status from this application (spec 3.3)."""
    candidate = db.get(Candidate, application.candidate_id)
    if candidate is None:
        return
    if application.status in _APP_TO_CANDIDATE_STATUS:
        candidate.status = _APP_TO_CANDIDATE_STATUS[application.status]
        return
    current = current_stage(application)
    if current is not None:
        candidate.status = _STAGE_TO_CANDIDATE_STATUS.get(current.stage.key, "active")


def _ordered(application: JobApplication) -> list[ApplicationStage]:
    return sorted(application.stages, key=lambda r: r.stage.position)


def _require_active(application: JobApplication) -> ApplicationStage:
    if application.status in TERMINAL:
        raise PipelineError(f"This application is already {application.status}.")
    current = current_stage(application)
    if current is None:
        raise PipelineError("This application has no stage in progress.")
    return current


def _next_enabled_round(rows: list[ApplicationStage], after: ApplicationStage) -> Optional[ApplicationStage]:
    """The next enabled round after `after`. Disabled rounds passed over are marked skipped."""
    for row in rows:
        if row.stage.position <= after.stage.position:
            continue
        if row.stage.kind != ROUND:
            continue
        if row.stage.enabled:
            return row
        if row.status == PENDING:
            row.status = SKIPPED
            row.completed_at = datetime.utcnow()
    return None


def _skip_pending(rows: list[ApplicationStage], now: datetime) -> None:
    for row in rows:
        if row.status == PENDING:
            row.status = SKIPPED
            row.completed_at = now


def _set_outcome(db: Session, application: JobApplication, outcome_key: str, status: str, now: datetime) -> None:
    rows = _ordered(application)
    for row in rows:
        if row.stage.key == outcome_key:
            row.status = PASSED
            row.started_at = now
            row.completed_at = now
    _skip_pending(rows, now)
    application.status = status
    sync_candidate_status(db, application)


def _close(row: ApplicationStage, status: str, now: datetime, actor_id: Optional[str], note: Optional[str]) -> None:
    row.status = status
    row.completed_at = now
    row.changed_by = actor_id
    row.note = note


def advance(db: Session, application: JobApplication, actor_id: Optional[str] = None, note: Optional[str] = None) -> None:
    """Current round passed; next enabled round in progress; last round hires."""
    current = _require_active(application)
    now = datetime.utcnow()
    _close(current, PASSED, now, actor_id, note)
    nxt = _next_enabled_round(_ordered(application), current)
    if nxt is None:
        _set_outcome(db, application, "hired", APP_HIRED, now)
        return
    nxt.status = IN_PROGRESS
    nxt.started_at = now
    on_stage_entered(db, nxt)
    sync_candidate_status(db, application)


def skip(db: Session, application: JobApplication, actor_id: Optional[str] = None, note: Optional[str] = None) -> None:
    """Current round skipped; next enabled round in progress. Refused on the last round."""
    current = _require_active(application)
    rows = _ordered(application)
    # Look ahead before touching anything so a refused skip leaves no trace.
    if not any(
        r.stage.position > current.stage.position and r.stage.kind == ROUND and r.stage.enabled
        for r in rows
    ):
        raise PipelineError("There is no later stage to skip to. Use Advance to mark the candidate hired.")
    nxt = _next_enabled_round(rows, current)
    now = datetime.utcnow()
    _close(current, SKIPPED, now, actor_id, note)
    nxt.status = IN_PROGRESS
    nxt.started_at = now
    on_stage_entered(db, nxt)
    sync_candidate_status(db, application)


def reject(db: Session, application: JobApplication, actor_id: Optional[str] = None, note: Optional[str] = None) -> None:
    """Current round failed; everything later skipped; application rejected."""
    current = _require_active(application)
    now = datetime.utcnow()
    _close(current, FAILED, now, actor_id, note)
    _skip_pending(_ordered(application), now)
    application.status = APP_REJECTED
    sync_candidate_status(db, application)


def decline(db: Session, application: JobApplication, actor_id: Optional[str] = None, note: Optional[str] = None) -> None:
    """Candidate declined an offer. Only valid at Offer or Offer accepted."""
    current = _require_active(application)
    if current.stage.key not in DECLINABLE_KEYS:
        raise PipelineError("A candidate can only decline once an offer has been made.")
    now = datetime.utcnow()
    _close(current, PASSED, now, actor_id, note)
    _set_outcome(db, application, "offer_declined", APP_DECLINED, now)


ACTIONS = {"advance": advance, "skip": skip, "reject": reject, "decline": decline}
