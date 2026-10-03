"""Notes on candidates (ATS Phase C, spec 2026-10-03 sections 3.1 and 5).

Plain `def` handlers (sync ORM, CLAUDE.md sharp edge). Writes are gated by
`ROUTE_PERMISSIONS` (PIPELINE_MOVE); reads by `visible_candidate_ids`, so an
interviewer only ever sees notes on candidates they are assigned to. Notes
never reach the scorer or any model prompt.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..models.intake import NoteCreate, NoteOut
from ..models.models import Candidate, JobApplication, Note, User
from ..services import pipeline_service as ps
from ..services.access_service import visible_candidate_ids
from ..services.feedback_service import display_name
from ..utils.auth import get_optional_user
from ..utils.database import get_db

router = APIRouter()


def candidate_or_404(db: Session, user: Optional[User], candidate_id: str) -> Candidate:
    """The candidate, or 404 when it does not exist or this user may not see it.

    One status for both on purpose: telling an interviewer "exists but not
    yours" would leak who is in the pipeline.
    """
    candidate = db.get(Candidate, candidate_id)
    visible = visible_candidate_ids(db, user)
    if candidate is None or (visible is not None and candidate_id not in visible):
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


def _author_name(author: Optional[User]) -> Optional[str]:
    # Phase B's display_name: a name or a role label, never an email address,
    # because the demo reads these notes too. None stays None so the UI can
    # say "Earlier note" for rows migrated from candidates.notes.
    if author is None:
        return None
    return display_name(author)


def _out(note: Note) -> NoteOut:
    application = note.application
    return NoteOut(
        id=note.id,
        candidate_id=note.candidate_id,
        body=note.body,
        created_at=note.created_at,
        author_name=_author_name(note.author),
        application_id=note.application_id,
        job_title=application.job.title if application is not None and application.job is not None else None,
        stage_name=note.stage.name if note.stage is not None else None,
    )


@router.get("/candidates/{candidate_id}/notes", response_model=List[NoteOut])
def list_notes(
    candidate_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> List[NoteOut]:
    """The candidate's notes thread, newest first."""
    candidate_or_404(db, user, candidate_id)
    notes = (
        db.query(Note)
        .options(
            joinedload(Note.author),
            joinedload(Note.stage),
            joinedload(Note.application).joinedload(JobApplication.job),
        )
        .filter(Note.candidate_id == candidate_id)
        .order_by(Note.created_at.desc(), Note.id.desc())
        .all()
    )
    return [_out(note) for note in notes]


@router.post("/candidates/{candidate_id}/notes", response_model=NoteOut, status_code=201)
def add_note(
    candidate_id: str,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> NoteOut:
    """Add a note about the person, one of their applications, or one stage of it."""
    candidate_or_404(db, user, candidate_id)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="A note needs some text.")
    if payload.stage_key and payload.application_id is None:
        raise HTTPException(status_code=422, detail="Pick the application a stage note belongs to.")

    application_id: Optional[int] = None
    stage_id: Optional[int] = None
    if payload.application_id is not None:
        application = db.get(JobApplication, payload.application_id)
        if application is None or application.candidate_id != candidate_id:
            raise HTTPException(status_code=422, detail="That application belongs to a different candidate.")
        application_id = application.id
        if payload.stage_key:
            stage = next(
                (s for s in ps.ensure_job_stages(db, application.job_id) if s.key == payload.stage_key),
                None,
            )
            if stage is None:
                raise HTTPException(
                    status_code=422, detail=f"This job has no stage named '{payload.stage_key}'."
                )
            stage_id = stage.id

    note = Note(
        candidate_id=candidate_id,
        application_id=application_id,
        stage_id=stage_id,
        author_id=user.id if user is not None else None,
        body=body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _out(note)
