"""Interview assignments and feedback (ATS Phase B, spec 2026-10-03 section 3.1).

Like pipeline_service, these mutate the session and never commit, so a router
composes them and commits once. Feedback is shown to people and never read by
the scorer; the transparency page publishes FEEDBACK_USED_FOR and
FEEDBACK_NEVER_USED_FOR, and test_feedback pins that the scoring modules do
not mention feedback at all.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import and_, func, null
from sqlalchemy.orm import Session

from backend.models.models import (
    ApplicationStage,
    Candidate,
    Feedback,
    FeedbackTemplate,
    Interview,
    Job,
    PipelineStage,
    StageDefaultInterviewer,
    User,
)
from backend.services import pipeline_service as ps
from backend.services.access_service import can_see_score
from backend.utils.auth import STAFF_ROLES
from backend.utils.permissions import role_label

MANUAL = "manual"
DEFAULT = "default"

RECOMMENDATIONS = ("strong_hire", "hire", "no_hire", "strong_no_hire")

# Track 2 Phase 4. A draft is visible only to its author, does not unlock
# score visibility, and leaves the interview pending.
DRAFT = "draft"
SUBMITTED = "submitted"

FEEDBACK_USED_FOR = [
    "Shown to the hiring team on the candidate's page, next to the stage it was given for.",
    "Counted on the Interviews page so nobody's feedback is forgotten.",
]
FEEDBACK_NEVER_USED_FOR = [
    "The match score. The ranker reads the candidate's profile and the job, never feedback.",
    "Search ranking, including the assistant's candidate search.",
    "Moving a candidate. Only a person presses Advance, Skip, Reject, or Decline.",
]

# Stage-row statuses at which the interview has happened (or is happening),
# so feedback is due.
_STARTED = (ps.IN_PROGRESS, ps.PASSED, ps.FAILED)


class FeedbackError(Exception):
    """A request the rules refuse. `status_code` is what the router returns."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def display_name(user: Optional[User]) -> str:
    """A person's name for screens other people see. Never their email: the
    demo can see these names, and a real admin account may have no name."""
    if user is None:
        return "Former team member"
    return user.name or role_label(user.role)


def candidate_name(candidate: Optional[Candidate]) -> str:
    if candidate is None:
        return "Unnamed candidate"
    return " ".join(p for p in (candidate.first_name, candidate.last_name) if p) or "Unnamed candidate"


def _team_member(user: Optional[User]) -> User:
    if user is None or user.role not in STAFF_ROLES:
        raise FeedbackError("Choose someone on the team.", 422)
    return user


def assign(db: Session, row: ApplicationStage, user: Optional[User], source: str = MANUAL) -> Interview:
    """Put `user` on this stage of this application. Idempotent."""
    user = _team_member(user)
    if row.stage.kind != ps.ROUND:
        raise FeedbackError("Interviewers are assigned to rounds, not outcomes.")
    if row.application.status in ps.TERMINAL:
        raise FeedbackError(f"This application is already {row.application.status}.")
    if row.status == ps.SKIPPED:
        raise FeedbackError("That stage was skipped for this candidate.")
    existing = next((i for i in row.interviews if i.interviewer_id == user.id), None)
    if existing is not None:
        return existing
    interview = Interview(interviewer_id=user.id, assignment_source=source, created_at=datetime.utcnow())
    row.interviews.append(interview)
    db.flush()
    return interview


def unassign(db: Session, interview: Interview) -> None:
    """A draft goes with the interview; submitted feedback stays."""
    if interview.submitted_feedback is not None:
        raise FeedbackError("Feedback has been submitted for this interview, so it stays on the record.")
    db.delete(interview)
    db.flush()


def apply_default_interviewers(db: Session, row: ApplicationStage) -> list[Interview]:
    """Called by pipeline_service.on_stage_entered when an application starts a round."""
    defaults = (
        db.query(StageDefaultInterviewer)
        .filter(StageDefaultInterviewer.pipeline_stage_id == row.stage_id)
        .order_by(StageDefaultInterviewer.id)
        .all()
    )
    out = []
    for default in defaults:
        if default.user is None or default.user.role not in STAFF_ROLES:
            continue
        out.append(assign(db, row, default.user, source=DEFAULT))
    return out


def set_default_interviewers(db: Session, stage: PipelineStage, user_ids: Iterable[str]) -> list[User]:
    """Replace the stage's default interviewers. Applies to applications that
    enter the stage from now on; nobody already there is reassigned."""
    if stage.kind != ps.ROUND:
        raise FeedbackError("Default interviewers belong to rounds, not outcomes.")
    users = [_team_member(db.get(User, user_id)) for user_id in dict.fromkeys(user_ids)]
    stage.default_interviewers.clear()
    db.flush()
    for user in users:
        stage.default_interviewers.append(StageDefaultInterviewer(user_id=user.id))
    db.flush()
    return users


def _writable_by(interview: Interview, user: User, verb: str) -> None:
    if interview.interviewer_id != user.id:
        raise FeedbackError(f"Only the assigned interviewer can {verb} this feedback.", 403)
    if interview.submitted_feedback is not None:
        raise FeedbackError("Feedback for this interview has already been submitted.")
    if interview.application_stage.status not in _STARTED:
        raise FeedbackError("This stage has not started yet, so there is nothing to give feedback on.")


def save_draft(
    db: Session,
    interview: Interview,
    user: User,
    rating: Optional[int],
    recommendation: Optional[str],
    notes: Optional[str],
) -> Feedback:
    """Create or overwrite the author's draft. Any field may be empty."""
    _writable_by(interview, user, "edit")
    if recommendation is not None and recommendation not in RECOMMENDATIONS:
        raise FeedbackError("Choose one of the four recommendations.", 422)
    if rating is not None and not 1 <= int(rating) <= 5:
        raise FeedbackError("A rating is from 1 to 5.", 422)
    feedback = interview.feedback
    if feedback is None:
        # null(), not None: the column has a server default, and the ORM leaves
        # a None out of the INSERT, which would stamp the draft as submitted.
        feedback = Feedback(status=DRAFT, submitted_at=null())
        interview.feedback = feedback
    feedback.rating = int(rating) if rating is not None else None
    feedback.recommendation = recommendation
    feedback.notes = notes or None
    feedback.updated_at = datetime.utcnow()
    db.flush()
    return feedback


def submit_feedback(
    db: Session,
    interview: Interview,
    user: User,
    rating: int,
    recommendation: str,
    notes: Optional[str],
) -> Feedback:
    """Final. Turns the author's draft, if any, into the submitted record."""
    _writable_by(interview, user, "submit")
    if recommendation not in RECOMMENDATIONS:
        raise FeedbackError("Choose one of the four recommendations.", 422)
    if not 1 <= int(rating) <= 5:
        raise FeedbackError("A rating is from 1 to 5.", 422)
    now = datetime.utcnow()
    feedback = interview.feedback
    if feedback is None:
        feedback = Feedback()
        interview.feedback = feedback
    feedback.status = SUBMITTED
    feedback.rating = int(rating)
    feedback.recommendation = recommendation
    feedback.notes = (notes or "").strip() or None
    feedback.submitted_at = now
    feedback.updated_at = now
    db.flush()
    return feedback


def interview_state(interview: Interview) -> str:
    """upcoming, waiting (for feedback), submitted, or skipped. A draft is still waiting."""
    if interview.submitted_feedback is not None:
        return "submitted"
    status = interview.application_stage.status
    if status in _STARTED:
        return "waiting"
    if status == ps.SKIPPED:
        return "skipped"
    return "upcoming"


def _pending_query(db: Session, interviewer_id: Optional[str]):
    query = (
        db.query(Interview)
        .join(ApplicationStage, Interview.application_stage_id == ApplicationStage.id)
        .outerjoin(Feedback, and_(Feedback.interview_id == Interview.id, Feedback.status == SUBMITTED))
        .filter(Feedback.id.is_(None), ApplicationStage.status.in_(_STARTED))
    )
    if interviewer_id is not None:
        query = query.filter(Interview.interviewer_id == interviewer_id)
    return query


def pending_feedback(db: Session, interviewer_id: Optional[str] = None) -> list[Interview]:
    """Interviews whose stage has started and that have no submitted feedback
    yet (a draft still counts as pending), oldest first."""
    return _pending_query(db, interviewer_id).order_by(ApplicationStage.started_at, Interview.id).all()


def pending_count(db: Session, interviewer_id: str) -> int:
    """How many feedback forms this person owes: the nav badge."""
    return _pending_query(db, interviewer_id).with_entities(func.count(Interview.id)).scalar() or 0


# --- templates ---------------------------------------------------------------


def list_templates(db: Session, job_id: Optional[int] = None) -> list[FeedbackTemplate]:
    """With `job_id`: that job's templates, then the global ones. Without:
    every template (pages that span jobs filter by job themselves)."""
    query = db.query(FeedbackTemplate)
    if job_id is not None:
        query = query.filter((FeedbackTemplate.job_id == job_id) | FeedbackTemplate.job_id.is_(None))
    # Job-specific first, then global; alphabetical inside each.
    return query.order_by(FeedbackTemplate.job_id.is_(None), FeedbackTemplate.name, FeedbackTemplate.id).all()


def create_template(db: Session, user: User, name: str, body: str, job_id: Optional[int]) -> FeedbackTemplate:
    if job_id is not None and db.get(Job, job_id) is None:
        raise FeedbackError("Job not found.", 404)
    template = FeedbackTemplate(
        name=name.strip(), body=body.strip(), job_id=job_id, created_by=user.id, updated_at=datetime.utcnow()
    )
    _require_text(template)
    db.add(template)
    db.flush()
    return template


def update_template(db: Session, template: FeedbackTemplate, name: str, body: str) -> FeedbackTemplate:
    template.name = name.strip()
    template.body = body.strip()
    _require_text(template)
    template.updated_at = datetime.utcnow()
    db.flush()
    return template


def _require_text(template: FeedbackTemplate) -> None:
    if not template.name or not template.body:
        raise FeedbackError("A template needs a name and some text.", 422)


def can_view_feedback(db: Session, viewer: Optional[User], interview: Interview) -> bool:
    """Your own feedback always; colleagues' under the same rule as the score."""
    if viewer is not None and interview.interviewer_id == viewer.id:
        return True
    return can_see_score(db, viewer, interview.application_stage.application.candidate_id)
