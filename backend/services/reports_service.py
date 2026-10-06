"""Reports and dashboard numbers (ATS Phase D, spec 2026-10-03 section 8).

Every function is a query over `application_stages`, joined to the pipeline
stage it belongs to and the application it is part of. Nothing is cached,
sampled, estimated, or projected, which is what lets the Reports page say
"every number is a query" and mean it.

Two rules hold throughout:

- `now` is always a parameter. Routers and assistant tools pass
  `datetime.utcnow()`; tests pass a fixed instant, so no assertion depends on
  the day the suite runs.
- `Scope` narrows every query the same way: to one job, and to the candidates
  the viewer may see (`access_service.visible_candidate_ids`, None meaning
  everyone). Every public function takes one, because a query that forgot it
  would show an interviewer people they are not assigned to.

Read only. Nothing here writes, flushes, or commits.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import Float, and_, case, cast, distinct, extract, func, literal_column, or_, select
from sqlalchemy.orm import Session, aliased

from backend.models.models import (
    ApplicationStage,
    Candidate,
    Feedback,
    Interview,
    Job,
    JobApplication,
    PipelineStage,
    User,
)
from backend.services import pipeline_service as ps
from backend.utils.auth import ROLE_INTERVIEWER

NO_MOVEMENT_DAYS = 7
LIST_LIMIT = 50
ACTIVITY_LIMIT = 20

# A stage counts as reached once the candidate started it, whatever came of
# it. Skipped stages were never reached.
REACHED = (ps.IN_PROGRESS, ps.PASSED, ps.FAILED)

# Rounds from this position on count toward the dashboard's "In interview or
# later" tile: everything after Resume submitted and Hiring manager review.
INTERVIEW_FROM_POSITION = 3

_DEFAULT_NAMES = {key: name for key, name, _kind, _description in ps.DEFAULT_STAGES}


@dataclass(frozen=True)
class Scope:
    """Which applications a query may count.

    `candidate_ids` None means no restriction; an empty set means nobody.
    """

    job_id: Optional[int] = None
    candidate_ids: Optional[frozenset] = None

    @classmethod
    def of(cls, job_id: Optional[int] = None, candidate_ids: Optional[Iterable[str]] = None) -> "Scope":
        return cls(
            job_id=job_id,
            candidate_ids=None if candidate_ids is None else frozenset(candidate_ids),
        )


def _scoped(query, scope: Scope):
    """Apply the scope. Every query below has job_applications in its FROM."""
    if scope.job_id is not None:
        query = query.filter(JobApplication.job_id == scope.job_id)
    if scope.candidate_ids is not None:
        query = query.filter(JobApplication.candidate_id.in_(sorted(scope.candidate_ids)))
    return query


def _stage_rows(db: Session, *columns):
    """application_stages joined to its stage and its application."""
    return (
        db.query(*columns)
        .select_from(ApplicationStage)
        .join(PipelineStage, PipelineStage.id == ApplicationStage.stage_id)
        .join(JobApplication, JobApplication.id == ApplicationStage.application_id)
    )


def _person(first: Optional[str], last: Optional[str]) -> str:
    return " ".join(part for part in (first, last) if part) or "Unnamed candidate"


def _title(title: Optional[str]) -> str:
    return title or "Untitled job"


def _stage_name(key: str, name: str, scope: Scope) -> str:
    # Across jobs a stage renamed on one job would show whichever name sorts
    # first; the default name is the one everybody recognises. Within one
    # job, that job's own name.
    if scope.job_id is None and key in _DEFAULT_NAMES:
        return _DEFAULT_NAMES[key]
    return name


def quarter_bounds(now: datetime, offset: int = 0) -> tuple[datetime, datetime, str]:
    """[start, end) of the calendar quarter holding `now`, moved by `offset` quarters."""
    index = now.year * 4 + (now.month - 1) // 3 + offset
    year, quarter = divmod(index, 4)
    end_year, end_quarter = divmod(index + 1, 4)
    return (
        datetime(year, quarter * 3 + 1, 1),
        datetime(end_year, end_quarter * 3 + 1, 1),
        f"Q{quarter + 1} {year}",
    )


def event_kind(stage_kind: str, stage_key: str, status: str) -> Optional[str]:
    """What a finished stage row means in the activity feed, or None for no event."""
    if stage_kind == ps.OUTCOME:
        if status != ps.PASSED:
            return None
        return {"hired": "hired", "offer_declined": "declined"}.get(stage_key, "passed")
    return {ps.PASSED: "passed", ps.FAILED: "rejected", ps.SKIPPED: "skipped"}.get(status)


def total_applications(db: Session, scope: Scope) -> int:
    return _scoped(db.query(func.count(JobApplication.id)), scope).scalar() or 0


def hired_applications(db: Session, scope: Scope) -> int:
    query = db.query(func.count(JobApplication.id)).filter(JobApplication.status == ps.APP_HIRED)
    return _scoped(query, scope).scalar() or 0


def stage_funnel(db: Session, scope: Scope) -> list[dict]:
    """Per round: applications that ever reached it, and those there right now.

    "Reached" means started (in progress, passed, or rejected there); a
    skipped round was never reached. "Here now" counts only active
    applications. Across jobs, rounds group by key in pipeline order.
    """
    ever = func.count(
        distinct(case((ApplicationStage.status.in_(REACHED), ApplicationStage.application_id)))
    )
    here = func.count(
        distinct(
            case(
                (
                    and_(
                        ApplicationStage.status == ps.IN_PROGRESS,
                        JobApplication.status == ps.APP_ACTIVE,
                    ),
                    ApplicationStage.application_id,
                )
            )
        )
    )
    position = func.min(PipelineStage.position)
    query = (
        _stage_rows(db, PipelineStage.key, position, func.min(PipelineStage.name), ever, here)
        .filter(PipelineStage.kind == ps.ROUND)
        .group_by(PipelineStage.key)
        .order_by(position, PipelineStage.key)
    )
    rows = _scoped(query, scope).all()
    total = total_applications(db, scope)
    return [
        {
            "key": key,
            "name": _stage_name(key, name, scope),
            "position": pos,
            "ever_reached": ever_reached,
            "currently_here": currently_here,
            "share_of_applicants": round(ever_reached / total, 3) if total else 0.0,
        }
        for key, pos, name, ever_reached, currently_here in rows
    ]


def time_in_stage(db: Session, scope: Scope) -> list[dict]:
    """Median days from entering a round to leaving it, per round.

    Counts rounds that ended (passed, or rejected there) with a real
    duration. Rows whose start and end are the same instant are left out:
    those are history rows written in one go (the Phase A migration backfill
    and the original seed), not time anybody spent. Rounds nobody has
    finished are not listed. Computed in Postgres with percentile_cont, so a
    median of two values is their midpoint.
    """
    days = cast(extract("epoch", ApplicationStage.completed_at - ApplicationStage.started_at), Float) / 86400.0
    position = func.min(PipelineStage.position)
    query = (
        _stage_rows(
            db,
            PipelineStage.key,
            position,
            func.min(PipelineStage.name),
            func.percentile_cont(0.5).within_group(days),
            func.count(ApplicationStage.id),
        )
        .filter(
            PipelineStage.kind == ps.ROUND,
            ApplicationStage.status.in_((ps.PASSED, ps.FAILED)),
            ApplicationStage.started_at.isnot(None),
            ApplicationStage.completed_at > ApplicationStage.started_at,
        )
        .group_by(PipelineStage.key)
        .order_by(position, PipelineStage.key)
    )
    return [
        {
            "key": key,
            "name": _stage_name(key, name, scope),
            "position": pos,
            "median_days": None if median is None else round(float(median), 2),
            "completed": completed,
        }
        for key, pos, name, median, completed in _scoped(query, scope).all()
    ]


def no_movement(
    db: Session,
    scope: Scope,
    now: datetime,
    days: int = NO_MOVEMENT_DAYS,
    limit: int = LIST_LIMIT,
) -> tuple[list[dict], int]:
    """Active applications whose current stage started more than `days` ago.

    Returns (longest waits first, capped at `limit`; total count).
    """
    cutoff = now - timedelta(days=days)
    query = (
        _stage_rows(
            db,
            ApplicationStage.started_at,
            JobApplication.id,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
            PipelineStage.key,
            PipelineStage.name,
        )
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .filter(
            ApplicationStage.status == ps.IN_PROGRESS,
            JobApplication.status == ps.APP_ACTIVE,
            ApplicationStage.started_at.isnot(None),
            ApplicationStage.started_at < cutoff,
        )
    )
    query = _scoped(query, scope)
    total = query.count()
    rows = query.order_by(ApplicationStage.started_at, JobApplication.id).limit(limit).all()
    return (
        [
            {
                "application_id": application_id,
                "candidate_id": candidate_id,
                "candidate_name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_key": stage_key,
                "stage_name": stage_name,
                "since": since,
                "days_waiting": (now - since).days,
            }
            for since, application_id, candidate_id, first, last, job_id, job_title, stage_key, stage_name in rows
        ],
        total,
    )


def pending_feedback(
    db: Session,
    scope: Scope,
    now: datetime,
    viewer: Optional[User] = None,
    limit: int = LIST_LIMIT,
) -> list[dict]:
    """Interviews on a stage the candidate has reached, with no feedback yet.

    Oldest first, by when the stage started. An interviewer sees only their
    own; every other viewer sees all of them. A skipped stage's interview is
    not pending: the round never happened.
    """
    interviewer = aliased(User)
    query = (
        db.query(
            Interview.id,
            interviewer.name,
            JobApplication.id,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
            PipelineStage.name,
            ApplicationStage.started_at,
            Interview.created_at,
        )
        .select_from(Interview)
        .join(ApplicationStage, ApplicationStage.id == Interview.application_stage_id)
        .join(PipelineStage, PipelineStage.id == ApplicationStage.stage_id)
        .join(JobApplication, JobApplication.id == ApplicationStage.application_id)
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .join(interviewer, interviewer.id == Interview.interviewer_id)
        # A draft is still pending (Track 2 Phase 4).
        .outerjoin(Feedback, and_(Feedback.interview_id == Interview.id, Feedback.status == "submitted"))
        .filter(Feedback.id.is_(None), ApplicationStage.status.in_(REACHED))
    )
    if viewer is not None and viewer.role == ROLE_INTERVIEWER:
        query = query.filter(Interview.interviewer_id == viewer.id)
    rows = (
        _scoped(query, scope)
        .order_by(ApplicationStage.started_at.asc().nulls_last(), Interview.id)
        .limit(limit)
        .all()
    )
    out = []
    for (
        interview_id,
        interviewer_name,
        application_id,
        candidate_id,
        first,
        last,
        job_id,
        job_title,
        stage_name,
        stage_started,
        assigned,
    ) in rows:
        since = stage_started or assigned
        out.append(
            {
                "interview_id": interview_id,
                "interviewer_name": interviewer_name,
                "application_id": application_id,
                "candidate_id": candidate_id,
                "candidate_name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_name": stage_name,
                "days_pending": max(0, (now - since).days) if since else 0,
            }
        )
    return out


def source_mix(db: Session, scope: Scope) -> list[dict]:
    """Applications and hires per application source, busiest first.

    The constants are literal SQL, not bound parameters, so the expression in
    SELECT and GROUP BY renders identically and Postgres accepts the grouping.
    """
    source = func.coalesce(
        func.nullif(func.lower(func.trim(JobApplication.source)), literal_column("''")),
        literal_column("'unknown'"),
    )
    applications = func.count(JobApplication.id)
    hired = func.count(case((JobApplication.status == ps.APP_HIRED, JobApplication.id)))
    query = db.query(source, applications, hired).group_by(source).order_by(applications.desc(), source)
    return [
        {"source": name, "applications": count, "hired": hires}
        for name, count, hires in _scoped(query, scope).all()
    ]


def outcomes_between(db: Session, scope: Scope, start: datetime, end: datetime, label: str) -> dict:
    """Hires, rejections, and declined offers recorded in [start, end)."""
    hires = func.count(
        case((and_(PipelineStage.key == "hired", ApplicationStage.status == ps.PASSED), ApplicationStage.id))
    )
    rejections = func.count(case((ApplicationStage.status == ps.FAILED, ApplicationStage.id)))
    declined = func.count(
        case(
            (
                and_(PipelineStage.key == "offer_declined", ApplicationStage.status == ps.PASSED),
                ApplicationStage.id,
            )
        )
    )
    query = _stage_rows(db, hires, rejections, declined).filter(
        ApplicationStage.completed_at >= start, ApplicationStage.completed_at < end
    )
    hired_count, rejected_count, declined_count = _scoped(query, scope).one()
    return {
        "label": label,
        "start": start,
        "end": end,
        "hires": hired_count,
        "rejections": rejected_count,
        "offers_declined": declined_count,
    }


def activity(db: Session, scope: Scope, limit: int = ACTIVITY_LIMIT) -> list[dict]:
    """The latest pipeline moves, newest first, from stage timestamps alone.

    Events: a first stage starting (an application arriving), a round passed
    or rejected, a round a person skipped, and an outcome reached. Two kinds
    of row are bookkeeping rather than events and are left out: stages
    skipped automatically (no changed_by) when an application ends or a
    disabled round is passed over, and the last round passing at the very
    instant the Hired or Offer declined outcome is recorded, where the
    outcome is the event.
    """
    actor = aliased(User)
    outcome = aliased(ApplicationStage)
    outcome_stage = aliased(PipelineStage)
    folded_into_outcome = (
        select(outcome.id)
        .join(outcome_stage, outcome_stage.id == outcome.stage_id)
        .where(
            outcome.application_id == ApplicationStage.application_id,
            outcome_stage.kind == ps.OUTCOME,
            outcome.status == ps.PASSED,
            outcome.completed_at == ApplicationStage.completed_at,
        )
        .exists()
    )
    completed = (
        _stage_rows(
            db,
            ApplicationStage.completed_at,
            ApplicationStage.status,
            PipelineStage.key,
            PipelineStage.kind,
            PipelineStage.name,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
            actor.name,
        )
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .outerjoin(actor, actor.id == ApplicationStage.changed_by)
        .filter(
            ApplicationStage.completed_at.isnot(None),
            or_(
                ApplicationStage.status.in_((ps.PASSED, ps.FAILED)),
                and_(ApplicationStage.status == ps.SKIPPED, ApplicationStage.changed_by.isnot(None)),
            ),
            ~and_(
                PipelineStage.kind == ps.ROUND,
                ApplicationStage.status == ps.PASSED,
                folded_into_outcome,
            ),
        )
    )
    completed = (
        _scoped(completed, scope)
        .order_by(ApplicationStage.completed_at.desc(), ApplicationStage.id.desc())
        .limit(limit)
        .all()
    )

    events = []
    for at, status, key, kind, stage_name, candidate_id, first, last, job_id, job_title, actor_name in completed:
        event = event_kind(kind, key, status)
        if event is None:
            continue
        events.append(
            {
                "at": at,
                "kind": event,
                "candidate_id": candidate_id,
                "candidate_name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_name": stage_name,
                "actor_name": actor_name,
            }
        )

    entered = (
        _stage_rows(
            db,
            ApplicationStage.started_at,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
        )
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .filter(PipelineStage.position == 1, ApplicationStage.started_at.isnot(None))
    )
    entered = (
        _scoped(entered, scope)
        .order_by(ApplicationStage.started_at.desc(), ApplicationStage.id.desc())
        .limit(limit)
        .all()
    )
    for at, candidate_id, first, last, job_id, job_title in entered:
        events.append(
            {
                "at": at,
                "kind": "applied",
                "candidate_id": candidate_id,
                "candidate_name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_name": None,
                "actor_name": None,
            }
        )

    # Stable sort: on an exact tie a completion stays ahead of an arrival.
    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]


def dashboard(db: Session, scope: Scope, now: datetime, viewer: Optional[User] = None) -> dict:
    """Everything the dashboard's pipeline cards need, in one call."""
    funnel = stage_funnel(db, scope)
    waiting, waiting_total = no_movement(db, scope, now, limit=8)
    interviewing = sum(
        row["currently_here"] for row in funnel if row["position"] >= INTERVIEW_FROM_POSITION
    )
    return {
        "generated_at": now,
        "total_applications": total_applications(db, scope),
        "interviewing_or_later": interviewing + hired_applications(db, scope),
        "funnel": funnel,
        "no_movement": waiting,
        "no_movement_total": waiting_total,
        "pending_feedback": pending_feedback(db, scope, now, viewer=viewer, limit=8),
        "activity": activity(db, scope, limit=12),
    }


def reports(db: Session, scope: Scope, now: datetime) -> dict:
    """Everything the Reports page needs, in one call."""
    waiting, waiting_total = no_movement(db, scope, now)
    return {
        "generated_at": now,
        "job_id": scope.job_id,
        "total_applications": total_applications(db, scope),
        "funnel": stage_funnel(db, scope),
        "time_in_stage": time_in_stage(db, scope),
        "no_movement": waiting,
        "no_movement_total": waiting_total,
        "source_mix": source_mix(db, scope),
        "quarters": [
            outcomes_between(db, scope, *quarter_bounds(now)),
            outcomes_between(db, scope, *quarter_bounds(now, offset=-1)),
        ],
    }


# The candidate-status words from spec 3.3, which people also use for stages.
STAGE_ALIASES = {
    "new": ("resume_submitted",),
    "applied": ("resume_submitted",),
    "screening": ("hm_review",),
    "interview": ("technical_written", "technical_interview", "problem_solving", "case_study", "hr_screen"),
    "interviewing": ("technical_written", "technical_interview", "problem_solving", "case_study", "hr_screen"),
    "interviews": ("technical_written", "technical_interview", "problem_solving", "case_study", "hr_screen"),
    "offered": ("offer", "offer_accepted"),
}


def normalize_stage_text(text: str) -> str:
    """'the HM-review stage' -> 'hm review'. Keys and names normalize the same way."""
    value = re.sub(r"[\s_\-]+", " ", str(text or "").lower()).strip()
    value = re.sub(r"^the ", "", value)
    value = re.sub(r" (stage|round|step)$", "", value)
    return value.strip()


def resolve_stage(db: Session, text: str, job_id: Optional[int] = None) -> tuple[list[str], dict]:
    """Map what someone typed to round keys.

    Returns (matched keys in pipeline order, every round key -> name). An
    alias wins, then an exact key or name, then every round whose key or
    name contains the words ("technical" matches both technical rounds).
    """
    query = db.query(PipelineStage.key, func.min(PipelineStage.name), func.min(PipelineStage.position)).filter(
        PipelineStage.kind == ps.ROUND
    )
    if job_id is not None:
        query = query.filter(PipelineStage.job_id == job_id)
    rows = query.group_by(PipelineStage.key).order_by(func.min(PipelineStage.position), PipelineStage.key).all()
    stages = {
        key: (_DEFAULT_NAMES.get(key, name) if job_id is None else name) for key, name, _position in rows
    }
    wanted = normalize_stage_text(text)
    if not wanted:
        return [], stages
    if wanted in STAGE_ALIASES:
        return [key for key in STAGE_ALIASES[wanted] if key in stages], stages
    exact = [
        key
        for key, name in stages.items()
        if wanted in (normalize_stage_text(key), normalize_stage_text(name))
    ]
    if exact:
        return exact, stages
    return [
        key
        for key, name in stages.items()
        if wanted in normalize_stage_text(name) or wanted in normalize_stage_text(key)
    ], stages


def candidates_at_stage(
    db: Session, keys: list[str], scope: Scope, now: datetime, limit: int = 25
) -> tuple[list[dict], int]:
    """Active applications in progress at any of `keys`, longest wait first.

    Each entry carries id and name (the candidate) and job_id and job_title,
    the shapes the assistant's link checker reads.
    """
    query = (
        _stage_rows(
            db,
            ApplicationStage.started_at,
            JobApplication.candidate_id,
            Candidate.first_name,
            Candidate.last_name,
            Job.id,
            Job.title,
            PipelineStage.name,
        )
        .join(Candidate, Candidate.id == JobApplication.candidate_id)
        .join(Job, Job.id == JobApplication.job_id)
        .filter(
            PipelineStage.key.in_(keys),
            ApplicationStage.status == ps.IN_PROGRESS,
            JobApplication.status == ps.APP_ACTIVE,
        )
    )
    query = _scoped(query, scope)
    total = query.count()
    rows = (
        query.order_by(ApplicationStage.started_at.asc().nulls_last(), Candidate.last_name, Candidate.first_name)
        .limit(limit)
        .all()
    )
    return (
        [
            {
                "id": candidate_id,
                "name": _person(first, last),
                "job_id": job_id,
                "job_title": _title(job_title),
                "stage_name": stage_name,
                "days_at_stage": (now - started).days if started else None,
            }
            for started, candidate_id, first, last, job_id, job_title, stage_name in rows
        ],
        total,
    )


def job_pipeline_state(
    db: Session,
    job_id: int,
    now: datetime,
    candidate_ids: Optional[Iterable[str]] = None,
    per_stage: int = 10,
) -> dict:
    """Who is at each enabled round of one job, plus outcome counts."""
    scope = Scope.of(job_id=job_id, candidate_ids=candidate_ids)
    rounds = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.job_id == job_id,
            PipelineStage.kind == ps.ROUND,
            PipelineStage.enabled.is_(True),
        )
        .order_by(PipelineStage.position)
        .all()
    )
    stages = []
    for stage in rounds:
        people, total = candidates_at_stage(db, [stage.key], scope, now, limit=per_stage)
        stages.append(
            {
                "stage": stage.name,
                "count": total,
                "candidates": [
                    {"id": p["id"], "name": p["name"], "days_at_stage": p["days_at_stage"]} for p in people
                ],
            }
        )
    status_counts = dict(
        _scoped(db.query(JobApplication.status, func.count(JobApplication.id)), scope)
        .group_by(JobApplication.status)
        .all()
    )
    _waiting, waiting_total = no_movement(db, scope, now, limit=1)
    in_progress = sum(s["count"] for s in stages)
    return {
        "in_progress": in_progress,
        # `count` too, so the golden replay's outcome check reads an empty
        # pipeline the same way it reads an empty search.
        "count": in_progress,
        "stage_counts": {s["stage"]: s["count"] for s in stages if s["count"]},
        "stages": stages,
        "outcomes": {
            status: status_counts.get(status, 0)
            for status in (ps.APP_HIRED, ps.APP_REJECTED, ps.APP_DECLINED, ps.APP_WITHDRAWN)
        },
        "no_movement_7_days": waiting_total,
    }
