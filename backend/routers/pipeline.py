"""Pipeline board and transitions (ATS Phase A, spec 2026-10-03 section 4).

Plain `def` handlers: they do sync ORM work and must not run on the event loop
(CLAUDE.md sharp edge). Writes are gated app-wide by `enforce_read_only`,
which grants them through the permission table (ATS Phase B: admin, hiring
manager, hiring team); nothing here needs to re-check that.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from ..models.models import ApplicationStage, Candidate, Job, JobApplication, User
from ..models.pipeline import (
    ApplicationCard,
    ApplicationDetail,
    ApplicationStageOut,
    BoardColumn,
    BulkItemResult,
    BulkTransitionRequest,
    BulkTransitionResponse,
    JobPipelineResponse,
    PipelineUpdateRequest,
    StageOut,
    TransitionRequest,
)
from ..services import applicant_fit, audit_service
from ..services import pipeline_service as ps
from ..services.access_service import request_user, visible_candidate_ids
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


def _stage_out(stage) -> StageOut:
    return StageOut(
        id=stage.id,
        key=stage.key,
        name=stage.name,
        kind=stage.kind,
        description=stage.description,
        position=stage.position,
        enabled=stage.enabled,
        custom=ps.is_custom(stage),
        movable=ps.is_movable(stage),
    )


def _board(
    db: Session, job: Job, user: Optional[User], visible: Optional[set[str]] = None
) -> JobPipelineResponse:
    stages = ps.ensure_job_stages(db, job.id)
    applications = (
        db.query(JobApplication)
        .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
        .filter(JobApplication.job_id == job.id)
        .all()
    )
    if visible is not None:
        applications = [a for a in applications if a.candidate_id in visible]
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
    # Track 2 Phase 2: each active card shows how well the person fits.
    fits = applicant_fit.score_applicants(
        db, job, [a.candidate_id for a in applications if a.status == ps.APP_ACTIVE], user
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
                    fit=fits.get(application.candidate_id),
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
        stages=[_stage_out(s) for s in stages],
        columns=columns,
        outcomes=outcomes,
    )


@router.get("/jobs/{job_id}/pipeline", response_model=JobPipelineResponse)
def get_job_pipeline(job_id: int, request: Request, db: Session = Depends(get_db)) -> JobPipelineResponse:
    """The job's stages and who is at each one (an interviewer sees only their candidates)."""
    user = request_user(request)
    visible = visible_candidate_ids(db, user)
    return _board(db, _job_or_404(db, job_id), user, visible)


@router.put("/jobs/{job_id}/pipeline", response_model=JobPipelineResponse)
def update_job_pipeline(
    job_id: int, payload: PipelineUpdateRequest, request: Request, db: Session = Depends(get_db)
) -> JobPipelineResponse:
    """Edit a job's stages in one transaction.

    Applied in a fixed order so one request can do everything the stage
    editor offers: remove added stages, enable/disable/rename, reorder the
    interview stages, then add new ones (placed by `after_key`, so they never
    need to appear in `order`). Any refusal rolls the whole request back.
    Outcomes and the first round stay enabled.
    """
    job = _job_or_404(db, job_id)
    try:
        for key in payload.remove:
            ps.remove_custom_stage(db, job.id, key)

        stages = {s.key: s for s in ps.ensure_job_stages(db, job.id)}
        for update in payload.stages:
            stage = stages.get(update.key)
            if stage is None:
                db.rollback()
                raise HTTPException(status_code=404, detail=f"No stage named '{update.key}' on this job.")
            if not update.enabled and (stage.kind == ps.OUTCOME or stage.key == ps.FIRST_ROUND):
                raise ps.PipelineError(f"'{stage.name}' cannot be turned off.")
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
                    raise ps.PipelineError(
                        f"{in_use} candidate(s) are at '{stage.name}' right now. Move them first."
                    )
            stage.enabled = update.enabled
            stage.name = update.name.strip()
            if update.description is not None:
                stage.description = update.description.strip() or None

        if payload.order is not None:
            ps.reorder_stages(db, job.id, payload.order)
        for new in payload.add:
            ps.add_custom_stage(db, job.id, new.name, new.description, new.after_key)
    except ps.PipelineError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return _board(db, job, request_user(request))


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int, db: Session = Depends(get_db)) -> ApplicationDetail:
    """One application with its full stage timeline."""
    application = _application_or_404(db, application_id)
    detail = _detail(db, application)
    db.commit()
    return detail


BULK_ACTIONS = ("advance", "reject")


@router.post("/applications/bulk/{action}", response_model=BulkTransitionResponse)
def bulk_transition(
    action: str,
    payload: BulkTransitionRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> BulkTransitionResponse:
    """Advance or reject many applications; each one succeeds or fails on its own.

    Every application runs in its own savepoint, so one that a colleague
    already rejected is reported by name instead of blocking the rest (ATS
    Phase C decision). Declared above the single-application route on
    purpose: that route's `{application_id}` would otherwise capture "bulk"
    and answer 422.
    """
    if action not in BULK_ACTIONS:
        raise HTTPException(status_code=404, detail=f"Bulk '{action}' is not available. Use advance or reject.")
    fn = ps.ACTIONS[action]
    note = (payload.note or "").strip() or None
    actor_id = user.id if user is not None else None
    audit_service.note(request, subject_ids=dict.fromkeys(payload.application_ids))

    results: list[BulkItemResult] = []
    for application_id in dict.fromkeys(payload.application_ids):
        application = (
            db.query(JobApplication)
            .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
            .filter(JobApplication.id == application_id)
            .first()
        )
        if application is None:
            results.append(BulkItemResult(application_id=application_id, ok=False, detail="Application not found."))
            continue
        candidate = db.get(Candidate, application.candidate_id)
        name = _name(candidate) if candidate else "Unnamed candidate"

        savepoint = db.begin_nested()
        try:
            ps.ensure_application_stages(db, application)
            fn(db, application, actor_id=actor_id, note=note)
            savepoint.commit()
        except ps.PipelineError as exc:
            savepoint.rollback()
            results.append(
                BulkItemResult(application_id=application_id, ok=False, candidate_name=name, detail=str(exc))
            )
            continue

        current = ps.current_stage(application)
        results.append(
            BulkItemResult(
                application_id=application_id,
                ok=True,
                candidate_name=name,
                status=application.status,
                current_stage_key=current.stage.key if current else None,
            )
        )

    db.commit()
    succeeded = sum(1 for r in results if r.ok)
    return BulkTransitionResponse(
        action=action, succeeded=succeeded, failed=len(results) - succeeded, results=results
    )


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
