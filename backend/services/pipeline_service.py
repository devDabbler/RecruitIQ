"""Every pipeline transition lives here (ATS Phase A, spec 2026-10-03 section 4).

Routers call these and nothing else touches `application_stages` or
`candidates.status`. The functions mutate the session but do not commit, so a
router can compose several and commit once; the tests run inside the
rolled-back fixture transaction the same way.
"""
from __future__ import annotations

import re
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
    # Track 2 Phase 3: the candidate pulled out (Withdraw, any active stage).
    ("withdrawn", "Withdrawn", "outcome", "You withdrew from the process."),
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

# Phase E: which stages may move. Resume submitted is where every
# application starts; Offer and Offer accepted carry the Decline rule; the
# outcomes are not rounds. Everything else is an "interview stage".
FIRST_ROUND = "resume_submitted"
OFFER_ROUNDS = ("offer", "offer_accepted")
CUSTOM_PREFIX = "custom_"
MAX_CUSTOM_STAGES = 10
LATE_STAGE_NOTE = "Added to the pipeline after this candidate had moved past this point."
MOVED_STAGE_NOTE = "Moved earlier in the pipeline after this candidate had passed this point."

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
    finished = application.status in TERMINAL and bool(existing)
    entered: Optional[ApplicationStage] = None
    for stage in stages:
        if stage.id in existing:
            continue
        row = ApplicationStage(application_id=application.id, stage_id=stage.id, status=PENDING)
        if finished:
            # A stage added after this application ended (an outcome added by
            # a later release) never happened for it.
            row.status = SKIPPED
            row.completed_at = now
        elif not started and stage.kind == ROUND and stage.enabled:
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
        # Unknown keys are custom stages, which always sit between Resume
        # submitted and the offer, so they are interview rounds.
        candidate.status = _STAGE_TO_CANDIDATE_STATUS.get(current.stage.key, "interviewing")


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
    """The next enabled, still-pending round after `after`.

    Rounds that were already decided (passed, failed, or skipped) are passed
    over, never re-opened: since Phase E a job can reorder its rounds, so a
    round that happened can sit after the current one. Disabled pending rounds
    passed over are marked skipped, as before.
    """
    for row in rows:
        if row.stage.position <= after.stage.position:
            continue
        if row.stage.kind != ROUND:
            continue
        if row.status != PENDING:
            continue
        if row.stage.enabled:
            return row
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
        r.stage.position > current.stage.position
        and r.stage.kind == ROUND
        and r.stage.enabled
        and r.status == PENDING
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


def withdraw(db: Session, application: JobApplication, actor_id: Optional[str] = None, note: Optional[str] = None) -> None:
    """The candidate pulled out (Track 2 Phase 3). Valid at any active stage.

    The current round is closed as skipped (it did not finish, and nobody
    failed it), the Withdrawn outcome is recorded, and every later stage is
    skipped. The reason note sits on the round they left from.
    """
    current = _require_active(application)
    now = datetime.utcnow()
    _close(current, SKIPPED, now, actor_id, note)
    _set_outcome(db, application, "withdrawn", APP_WITHDRAWN, now)


ACTIONS = {"advance": advance, "skip": skip, "reject": reject, "decline": decline, "withdraw": withdraw}


# --- custom stages and reordering (ATS Phase E) --------------------------------


def is_custom(stage: PipelineStage) -> bool:
    return stage.key.startswith(CUSTOM_PREFIX)


def is_movable(stage: PipelineStage) -> bool:
    return stage.kind == ROUND and stage.key != FIRST_ROUND and stage.key not in OFFER_ROUNDS


def _custom_key(existing: set[str], name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "stage"
    key = f"{CUSTOM_PREFIX}{slug}"
    n = 2
    while key in existing:
        key = f"{CUSTOM_PREFIX}{slug}_{n}"
        n += 1
    return key


def _layout(stages: list[PipelineStage], middle_keys: list[str]) -> list[PipelineStage]:
    """First round, interview stages in the given order, offer rounds, outcomes."""
    by_key = {s.key: s for s in stages}
    if FIRST_ROUND not in by_key or any(k not in by_key for k in OFFER_ROUNDS):
        raise PipelineError("This job is missing a default stage, so its stages cannot be rearranged.")
    outcomes = [s for s in sorted(stages, key=lambda s: s.position) if s.kind == OUTCOME]
    return [by_key[FIRST_ROUND], *(by_key[k] for k in middle_keys), *(by_key[k] for k in OFFER_ROUNDS), *outcomes]


def _renumber(stages_in_order: list[PipelineStage]) -> None:
    for position, stage in enumerate(stages_in_order, start=1):
        stage.position = position


def _backfill_new_stage(db: Session, stage: PipelineStage) -> None:
    """One row per existing application for a stage added mid-flight."""
    now = datetime.utcnow()
    applications = db.query(JobApplication).filter(JobApplication.job_id == stage.job_id).all()
    for application in applications:
        if not application.stages:
            continue  # ensure_application_stages builds a full set on first read
        current = current_stage(application)
        behind = application.status in TERMINAL or (
            current is not None and current.stage.position > stage.position
        )
        row = ApplicationStage(
            application_id=application.id,
            stage_id=stage.id,
            status=SKIPPED if behind else PENDING,
        )
        if behind:
            row.completed_at = now
            row.note = LATE_STAGE_NOTE
        db.add(row)
    db.flush()
    for application in applications:
        db.expire(application, ["stages"])


def add_custom_stage(
    db: Session,
    job_id: int,
    name: str,
    description: Optional[str] = None,
    after_key: Optional[str] = None,
) -> PipelineStage:
    """A new interview stage, placed after `after_key` (default: just before the offer)."""
    stages = ensure_job_stages(db, job_id)
    name = (name or "").strip()
    if not name:
        raise PipelineError("A stage needs a name.")
    if sum(1 for s in stages if is_custom(s)) >= MAX_CUSTOM_STAGES:
        raise PipelineError(f"A job can have at most {MAX_CUSTOM_STAGES} added stages.")

    middle = [s.key for s in stages if is_movable(s)]
    if after_key is None:
        index = len(middle)
    elif after_key == FIRST_ROUND:
        index = 0
    elif after_key in middle:
        index = middle.index(after_key) + 1
    else:
        raise PipelineError(
            "New stages go after Resume submitted or after another interview stage, never after the offer."
        )

    stage = PipelineStage(
        job_id=job_id,
        key=_custom_key({s.key for s in stages}, name),
        name=name,
        description=(description or "").strip() or None,
        kind=ROUND,
        position=0,
        enabled=True,
    )
    db.add(stage)
    db.flush()
    middle.insert(index, stage.key)
    _renumber(_layout([*stages, stage], middle))
    db.flush()
    _backfill_new_stage(db, stage)
    return stage


def _close_rows_left_behind(db: Session, job_id: int) -> None:
    now = datetime.utcnow()
    applications = (
        db.query(JobApplication)
        .filter(JobApplication.job_id == job_id, JobApplication.status == APP_ACTIVE)
        .all()
    )
    for application in applications:
        current = current_stage(application)
        if current is None:
            continue
        for row in application.stages:
            if (
                row.status == PENDING
                and row.stage.kind == ROUND
                and row.stage.position < current.stage.position
            ):
                row.status = SKIPPED
                row.completed_at = now
                row.note = MOVED_STAGE_NOTE


def reorder_stages(db: Session, job_id: int, middle_order: list[str]) -> None:
    """Put the interview stages in `middle_order`. The pinned stages do not move."""
    stages = ensure_job_stages(db, job_id)
    middle = [s.key for s in stages if is_movable(s)]
    if len(middle_order) != len(set(middle_order)) or set(middle_order) != set(middle):
        raise PipelineError(
            "The new order must list every interview stage exactly once. "
            "Resume submitted stays first and the offer stages stay last."
        )
    _renumber(_layout(stages, middle_order))
    db.flush()
    _close_rows_left_behind(db, job_id)
    db.flush()


def remove_custom_stage(db: Session, job_id: int, key: str) -> None:
    """Delete a stage this job added, if no candidate has history at it."""
    stages = ensure_job_stages(db, job_id)
    stage = next((s for s in stages if s.key == key), None)
    if stage is None:
        raise PipelineError(f"No stage named '{key}' on this job.")
    if not is_custom(stage):
        raise PipelineError(f"'{stage.name}' is a default stage. Turn it off instead of removing it.")
    rows = db.query(ApplicationStage).filter(ApplicationStage.stage_id == stage.id).all()
    if any(r.status in (IN_PROGRESS, PASSED, FAILED) for r in rows):
        raise PipelineError(
            f"'{stage.name}' already has candidate history. Turn it off instead of removing it."
        )
    application_ids = {r.application_id for r in rows}
    for row in rows:
        db.delete(row)
    db.delete(stage)
    db.flush()
    _renumber([s for s in stages if s.id != stage.id])
    db.flush()
    if application_ids:
        for application in db.query(JobApplication).filter(JobApplication.id.in_(application_ids)).all():
            db.expire(application, ["stages"])
