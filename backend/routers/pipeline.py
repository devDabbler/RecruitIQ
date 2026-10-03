"""Pipeline board and transitions (ATS Phase A, spec 2026-10-03 section 4).

Plain `def` handlers: they do sync ORM work and must not run on the event loop
(CLAUDE.md sharp edge). Writes are admin-only through the app-wide
`enforce_read_only` gate; nothing here needs to re-check that.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..models.models import ApplicationStage, Candidate, Job, JobApplication, User
from ..models.pipeline import (
    ApplicationCard,
    ApplicationDetail,
    ApplicationStageOut,
    BoardColumn,
    JobPipelineResponse,
    PipelineUpdateRequest,
    StageOut,
    TransitionRequest,
)
from ..services import pipeline_service as ps
from ..utils.auth import get_optional_user
from ..utils.database import get_db

router = APIRouter()


def _name(candidate: Candidate) -> str:
    return " ".join(part for part in (candidate.first_name, candidate.last_name) if part) or "Unnamed candidate"


def _job_or_404(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _application_or_404(db: Session, application_id: int) -> JobApplication:
    application = (
        db.query(JobApplication)
        .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
        .filter(JobApplication.id == application_id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _detail(db: Session, application: JobApplication) -> ApplicationDetail:
    rows = ps.ensure_application_stages(db, application)
    candidate = db.get(Candidate, application.candidate_id)
    job = db.get(Job, application.job_id)
    current = ps.current_stage(application)
    return ApplicationDetail(
        id=application.id,
        job_id=application.job_id,
        job_title=job.title if job else "",
        candidate_id=application.candidate_id,
        candidate_name=_name(candidate) if candidate else "Unnamed candidate",
        status=application.status,
        current_stage_key=current.stage.key if current else None,
        current_stage_name=current.stage.name if current else None,
        applied_at=application.applied_at,
        stages=[
            ApplicationStageOut(
                key=row.stage.key,
                name=row.stage.name,
                kind=row.stage.kind,
                description=row.stage.description,
                enabled=row.stage.enabled,
                status=row.status,
                started_at=row.started_at,
                completed_at=row.completed_at,
                note=row.note,
            )
            for row in rows
        ],
    )


def _board(db: Session, job: Job) -> JobPipelineResponse:
    stages = ps.ensure_job_stages(db, job.id)
    applications = (
        db.query(JobApplication)
        .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
        .filter(JobApplication.job_id == job.id)
        .all()
    )
    for application in applications:
        ps.ensure_application_stages(db, application)
    db.commit()

    candidates = (
        {
            c.id: c
            for c in db.query(Candidate)
            .filter(Candidate.id.in_([a.candidate_id for a in applications]))
            .all()
        }
        if applications
        else {}
    )

    columns = []
    for stage in stages:
        if stage.kind != ps.ROUND or not stage.enabled:
            continue
        cards = []
        for application in applications:
            if application.status != ps.APP_ACTIVE:
                continue
            current = ps.current_stage(application)
            if current is None or current.stage_id != stage.id:
                continue
            candidate = candidates.get(application.candidate_id)
            cards.append(
                ApplicationCard(
                    application_id=application.id,
                    candidate_id=application.candidate_id,
                    candidate_name=_name(candidate) if candidate else "Unnamed candidate",
                    current_position=candidate.current_position if candidate else None,
                    entered_at=current.started_at,
                )
            )
        cards.sort(key=lambda c: (c.entered_at or datetime.min, c.candidate_name))
        columns.append(BoardColumn(stage_key=stage.key, stage_name=stage.name, applications=cards))

    outcomes = {"hired": 0, "rejected": 0, "declined": 0}
    for application in applications:
        if application.status in outcomes:
            outcomes[application.status] += 1

    return JobPipelineResponse(
        job_id=job.id,
        stages=[StageOut.model_validate(s) for s in stages],
        columns=columns,
        outcomes=outcomes,
    )


@router.get("/jobs/{job_id}/pipeline", response_model=JobPipelineResponse)
def get_job_pipeline(job_id: int, db: Session = Depends(get_db)) -> JobPipelineResponse:
    """The job's stages and who is at each one."""
    return _board(db, _job_or_404(db, job_id))


@router.put("/jobs/{job_id}/pipeline", response_model=JobPipelineResponse)
def update_job_pipeline(
    job_id: int, payload: PipelineUpdateRequest, db: Session = Depends(get_db)
) -> JobPipelineResponse:
    """Enable, disable, or rename stages. Outcomes and the first round stay enabled."""
    job = _job_or_404(db, job_id)
    stages = {s.key: s for s in ps.ensure_job_stages(db, job.id)}
    for update in payload.stages:
        stage = stages.get(update.key)
        if stage is None:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"No stage named '{update.key}' on this job.")
        if not update.enabled and (stage.kind == ps.OUTCOME or stage.position == 1):
            db.rollback()
            raise HTTPException(status_code=409, detail=f"'{stage.name}' cannot be turned off.")
        if not update.enabled and stage.enabled:
            in_use = (
                db.query(ApplicationStage)
                .join(JobApplication)
                .filter(
                    ApplicationStage.stage_id == stage.id,
                    ApplicationStage.status == ps.IN_PROGRESS,
                    JobApplication.status == ps.APP_ACTIVE,
                )
                .count()
            )
            if in_use:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=f"{in_use} candidate(s) are at '{stage.name}' right now. Move them first.",
                )
        stage.enabled = update.enabled
        stage.name = update.name.strip()
        if update.description is not None:
            stage.description = update.description.strip() or None
    db.commit()
    return _board(db, job)


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int, db: Session = Depends(get_db)) -> ApplicationDetail:
    """One application with its full stage timeline."""
    application = _application_or_404(db, application_id)
    detail = _detail(db, application)
    db.commit()
    return detail


@router.post("/applications/{application_id}/{action}", response_model=ApplicationDetail)
def transition_application(
    application_id: int,
    action: str,
    payload: TransitionRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> ApplicationDetail:
    """Advance, skip, reject, or decline. One transaction; 409 when not allowed."""
    fn = ps.ACTIONS.get(action)
    if fn is None:
        raise HTTPException(status_code=404, detail=f"Unknown action '{action}'.")
    application = _application_or_404(db, application_id)
    ps.ensure_application_stages(db, application)
    note = (payload.note or "").strip() or None
    try:
        fn(db, application, actor_id=user.id if user else None, note=note)
    except ps.PipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(application)
    return _detail(db, application)
