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

from sqlalchemy.orm import Session

from backend.models.models import (
    ApplicationStage,
    Candidate,
    Feedback,
    Interview,
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
    if interview.feedback is not None:
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


def submit_feedback(
    db: Session,
    interview: Interview,
    user: User,
    rating: int,
    recommendation: str,
    notes: Optional[str],
) -> Feedback:
    if interview.interviewer_id != user.id:
        raise FeedbackError("Only the assigned interviewer can submit this feedback.", 403)
    if interview.feedback is not None:
        raise FeedbackError("Feedback for this interview has already been submitted.")
    if interview.application_stage.status not in _STARTED:
        raise FeedbackError("This stage has not started yet, so there is nothing to give feedback on.")
    if recommendation not in RECOMMENDATIONS:
        raise FeedbackError("Choose one of the four recommendations.", 422)
    if not 1 <= int(rating) <= 5:
        raise FeedbackError("A rating is from 1 to 5.", 422)
    feedback = Feedback(
        rating=int(rating),
        recommendation=recommendation,
        notes=(notes or "").strip() or None,
        submitted_at=datetime.utcnow(),
    )
    interview.feedback = feedback
    db.flush()
    return feedback


def interview_state(interview: Interview) -> str:
    """upcoming, waiting (for feedback), submitted, or skipped."""
    if interview.feedback is not None:
        return "submitted"
    status = interview.application_stage.status
    if status in _STARTED:
        return "waiting"
    if status == ps.SKIPPED:
        return "skipped"
    return "upcoming"


def pending_feedback(db: Session, interviewer_id: Optional[str] = None) -> list[Interview]:
    """Interviews whose stage has started and that have no feedback yet, oldest first."""
    query = (
        db.query(Interview)
        .join(ApplicationStage, Interview.application_stage_id == ApplicationStage.id)
        .outerjoin(Feedback, Feedback.interview_id == Interview.id)
        .filter(Feedback.id.is_(None), ApplicationStage.status.in_(_STARTED))
    )
    if interviewer_id is not None:
        query = query.filter(Interview.interviewer_id == interviewer_id)
    return query.order_by(ApplicationStage.started_at, Interview.id).all()


def can_view_feedback(db: Session, viewer: Optional[User], interview: Interview) -> bool:
    """Your own feedback always; colleagues' under the same rule as the score."""
    if viewer is not None and interview.interviewer_id == viewer.id:
        return True
    return can_see_score(db, viewer, interview.application_stage.application.candidate_id)
