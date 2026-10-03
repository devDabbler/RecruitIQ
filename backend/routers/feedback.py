"""Interviews, feedback, and default interviewers (ATS Phase B).

Plain `def` handlers: they do sync ORM work (CLAUDE.md sharp edge). Writes
are gated app-wide by `enforce_read_only` through ROUTE_PERMISSIONS; the
handlers that need the acting user take it from `require(...)`, which restates
the permission where the route is defined.

Mounted *before* the pipeline router in main.py: Phase A's
`POST /applications/{id}/{action}` would otherwise swallow
`POST /applications/{id}/interviews` as an unknown action.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..models.feedback import (
    AssignRequest,
    DefaultInterviewersRequest,
    DefaultInterviewersResponse,
    FeedbackIn,
    FeedbackOut,
    InterviewListItem,
    InterviewListResponse,
    InterviewOut,
    StageDefaults,
    TeamMemberBrief,
)
from ..models.models import Candidate, Interview, Job, JobApplication, User
from ..models.team import MessageOut
from ..services import feedback_service as fs
from ..services import pipeline_service as ps
from ..services.access_service import can_see_score, request_user
from ..utils.auth import ROLE_INTERVIEWER, request_identity
from ..utils.database import get_db
from ..utils.permissions import FEEDBACK_SUBMIT, JOBS_WRITE, PIPELINE_MOVE, require

router = APIRouter()

_STATE_ORDER = {"waiting": 0, "upcoming": 1, "submitted": 2, "skipped": 3}


def _refuse(db: Session, exc: fs.FeedbackError) -> None:
    db.rollback()
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


def _application_or_404(db: Session, application_id: int) -> JobApplication:
    application = db.get(JobApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _interview_or_404(db: Session, interview_id: int) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


def _interview_out(db: Session, interview: Interview, viewer: Optional[User]) -> InterviewOut:
    row = interview.application_stage
    feedback = interview.feedback
    visible = fs.can_view_feedback(db, viewer, interview)
    return InterviewOut(
        id=interview.id,
        application_id=row.application_id,
        stage_key=row.stage.key,
        stage_name=row.stage.name,
        stage_status=row.status,
        state=fs.interview_state(interview),
        interviewer_id=interview.interviewer_id,
        interviewer_name=fs.display_name(interview.interviewer),
        assignment_source=interview.assignment_source,
        feedback=(
            FeedbackOut(
                rating=feedback.rating,
                recommendation=feedback.recommendation,
                notes=feedback.notes,
                submitted_at=feedback.submitted_at,
            )
            if feedback is not None and visible
            else None
        ),
        feedback_hidden=feedback is not None and not visible,
    )


def _list_item(db: Session, interview: Interview, viewer: Optional[User]) -> InterviewListItem:
    application = interview.application_stage.application
    job = db.get(Job, application.job_id)
    return InterviewListItem(
        **_interview_out(db, interview, viewer).model_dump(),
        candidate_id=application.candidate_id,
        candidate_name=fs.candidate_name(db.get(Candidate, application.candidate_id)),
        job_id=application.job_id,
        job_title=job.title if job else "",
        score_visible=can_see_score(db, viewer, application.candidate_id),
    )


def _brief(user: User) -> TeamMemberBrief:
    return TeamMemberBrief(id=user.id, name=fs.display_name(user), role=user.role)


def _defaults(db: Session, job: Job) -> DefaultInterviewersResponse:
    stages = ps.ensure_job_stages(db, job.id)
    return DefaultInterviewersResponse(
        job_id=job.id,
        stages=[
            StageDefaults(
                stage_key=stage.key,
                stage_name=stage.name,
                users=[_brief(d.user) for d in stage.default_interviewers if d.user is not None],
            )
            for stage in stages
            if stage.kind == ps.ROUND and stage.enabled
        ],
    )


@router.get("/applications/{application_id}/interviews", response_model=list[InterviewOut])
def list_application_interviews(
    application_id: int, request: Request, db: Session = Depends(get_db)
) -> list[InterviewOut]:
    """Everyone assigned to this application, stage by stage, with feedback
    where the viewer may read it."""
    application = _application_or_404(db, application_id)
    rows = ps.ensure_application_stages(db, application)
    viewer = request_user(request)
    out = [_interview_out(db, interview, viewer) for row in rows for interview in row.interviews]
    db.commit()
    return out


@router.post(
    "/applications/{application_id}/interviews",
    response_model=InterviewOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_interviewer(
    application_id: int,
    payload: AssignRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require(PIPELINE_MOVE)),
) -> InterviewOut:
    application = _application_or_404(db, application_id)
    rows = ps.ensure_application_stages(db, application)
    row = next((r for r in rows if r.stage.key == payload.stage_key), None)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No stage named '{payload.stage_key}' on this job.")
    try:
        interview = fs.assign(db, row, db.get(User, payload.interviewer_id))
    except fs.FeedbackError as exc:
        _refuse(db, exc)
    db.commit()
    return _interview_out(db, interview, actor)


@router.delete("/interviews/{interview_id}", response_model=MessageOut)
def unassign_interviewer(
    interview_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require(PIPELINE_MOVE)),
) -> MessageOut:
    interview = _interview_or_404(db, interview_id)
    name = fs.display_name(interview.interviewer)
    try:
        fs.unassign(db, interview)
    except fs.FeedbackError as exc:
        _refuse(db, exc)
    db.commit()
    return MessageOut(message=f"Removed {name} from this stage.")


@router.post("/interviews/{interview_id}/feedback", response_model=InterviewOut)
def submit_feedback(
    interview_id: int,
    payload: FeedbackIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require(FEEDBACK_SUBMIT)),
) -> InterviewOut:
    interview = _interview_or_404(db, interview_id)
    try:
        fs.submit_feedback(db, interview, actor, payload.rating, payload.recommendation, payload.notes)
    except fs.FeedbackError as exc:
        _refuse(db, exc)
    db.commit()
    return _interview_out(db, interview, actor)


@router.get("/interviews", response_model=InterviewListResponse)
def list_interviews(
    request: Request,
    scope: Literal["mine", "pending", "all"] = Query("mine"),
    db: Session = Depends(get_db),
) -> InterviewListResponse:
    """`mine` for anyone signed in, `pending` and `all` for everyone but interviewers."""
    role, user = request_identity(request, db)
    if role == ROLE_INTERVIEWER and scope != "mine":
        raise HTTPException(status_code=403, detail="Interviewers see their own interviews.")
    if scope == "pending":
        interviews = fs.pending_feedback(db)
    elif scope == "mine":
        if user is None:
            return InterviewListResponse(items=[])
        interviews = db.query(Interview).filter(Interview.interviewer_id == user.id).all()
    else:
        interviews = db.query(Interview).order_by(Interview.created_at.desc()).limit(200).all()
    items = [_list_item(db, interview, user) for interview in interviews]
    if scope != "pending":
        items.sort(key=lambda i: (_STATE_ORDER.get(i.state, 9), i.candidate_name))
    return InterviewListResponse(items=items)


@router.get("/jobs/{job_id}/default-interviewers", response_model=DefaultInterviewersResponse)
def get_default_interviewers(job_id: int, db: Session = Depends(get_db)) -> DefaultInterviewersResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    out = _defaults(db, job)
    db.commit()
    return out


@router.put(
    "/jobs/{job_id}/stages/{stage_key}/default-interviewers",
    response_model=DefaultInterviewersResponse,
)
def set_default_interviewers(
    job_id: int,
    stage_key: str,
    payload: DefaultInterviewersRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require(JOBS_WRITE)),
) -> DefaultInterviewersResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    stage = next((s for s in ps.ensure_job_stages(db, job.id) if s.key == stage_key), None)
    if stage is None:
        raise HTTPException(status_code=404, detail=f"No stage named '{stage_key}' on this job.")
    try:
        fs.set_default_interviewers(db, stage, payload.user_ids)
    except fs.FeedbackError as exc:
        _refuse(db, exc)
    db.commit()
    return _defaults(db, job)
