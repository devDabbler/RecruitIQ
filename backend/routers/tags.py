"""Tags on candidates (ATS Phase C, bulk tagging Track 2 Phase 5).

Writes are gated by `ROUTE_PERMISSIONS` (PIPELINE_MOVE); reads by
`visible_candidate_ids` through `notes.candidate_or_404`.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.intake import (
    BulkTagItem,
    BulkTagRequest,
    BulkTagResponse,
    CandidateTagsResponse,
    TagCount,
    TagCreate,
)
from ..models.models import Candidate, CandidateTag, User
from ..services import audit_service
from ..services.access_service import visible_candidate_ids
from ..utils.auth import get_optional_user
from ..utils.database import get_db
from ..utils.tags import normalize_tag
from .notes import candidate_or_404

router = APIRouter()

MAX_TAGS_PER_CANDIDATE = 20


def _tags(db: Session, candidate_id: str) -> List[str]:
    rows = (
        db.query(CandidateTag.tag)
        .filter(CandidateTag.candidate_id == candidate_id)
        .order_by(CandidateTag.tag)
        .all()
    )
    return [tag for (tag,) in rows]


def _limit_message() -> str:
    return f"A candidate can carry at most {MAX_TAGS_PER_CANDIDATE} tags. Remove one first."


def _name(candidate: Candidate) -> str:
    return " ".join(p for p in (candidate.first_name, candidate.last_name) if p) or "Unnamed candidate"


@router.post("/candidates/bulk/tag", response_model=BulkTagResponse)
def bulk_tag(
    payload: BulkTagRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> BulkTagResponse:
    """Give many candidates one tag; each one succeeds or fails on its own.

    Every candidate runs in its own savepoint, like the bulk pipeline moves,
    so one at the tag limit is reported by name instead of blocking the
    rest. A candidate who already has the tag counts as done. Works from any
    candidate list, not only one filtered to a job.
    """
    try:
        tag = normalize_tag(payload.tag)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    ids = list(dict.fromkeys(payload.candidate_ids))
    audit_service.note(request, subject_ids=ids)
    visible = visible_candidate_ids(db, user)

    results: list[BulkTagItem] = []
    for candidate_id in ids:
        candidate = db.get(Candidate, candidate_id)
        if candidate is None or (visible is not None and candidate_id not in visible):
            results.append(BulkTagItem(candidate_id=candidate_id, ok=False, detail="Candidate not found."))
            continue
        name = _name(candidate)
        current = _tags(db, candidate_id)
        if tag in current:
            results.append(BulkTagItem(candidate_id=candidate_id, ok=True, candidate_name=name))
            continue
        if len(current) >= MAX_TAGS_PER_CANDIDATE:
            results.append(
                BulkTagItem(candidate_id=candidate_id, ok=False, candidate_name=name, detail=_limit_message())
            )
            continue
        savepoint = db.begin_nested()
        try:
            db.add(CandidateTag(candidate_id=candidate_id, tag=tag))
            db.flush()
            savepoint.commit()
        except IntegrityError:
            # A colleague tagged them in the same instant: the unique key says
            # the tag is there, which is what was asked for.
            savepoint.rollback()
            ok = tag in _tags(db, candidate_id)
            results.append(
                BulkTagItem(
                    candidate_id=candidate_id,
                    ok=ok,
                    candidate_name=name,
                    detail=None if ok else "Could not tag this candidate. Try again.",
                )
            )
            continue
        results.append(BulkTagItem(candidate_id=candidate_id, ok=True, candidate_name=name))

    db.commit()
    succeeded = sum(1 for r in results if r.ok)
    return BulkTagResponse(tag=tag, succeeded=succeeded, failed=len(results) - succeeded, results=results)


@router.get("/candidates/{candidate_id}/tags", response_model=CandidateTagsResponse)
def list_candidate_tags(
    candidate_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> CandidateTagsResponse:
    candidate_or_404(db, user, candidate_id)
    return CandidateTagsResponse(candidate_id=candidate_id, tags=_tags(db, candidate_id))


@router.post("/candidates/{candidate_id}/tags", response_model=CandidateTagsResponse)
def add_candidate_tag(
    candidate_id: str,
    payload: TagCreate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> CandidateTagsResponse:
    """Add one tag, normalized. Adding a tag the candidate already has is a no-op."""
    candidate_or_404(db, user, candidate_id)
    try:
        tag = normalize_tag(payload.tag)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    current = _tags(db, candidate_id)
    if tag not in current:
        if len(current) >= MAX_TAGS_PER_CANDIDATE:
            raise HTTPException(status_code=409, detail=_limit_message())
        db.add(CandidateTag(candidate_id=candidate_id, tag=tag))
        db.commit()
    return CandidateTagsResponse(candidate_id=candidate_id, tags=_tags(db, candidate_id))


@router.delete("/candidates/{candidate_id}/tags/{tag}", response_model=CandidateTagsResponse)
def remove_candidate_tag(
    candidate_id: str,
    tag: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> CandidateTagsResponse:
    """Remove one tag. Idempotent: removing a tag that is not there is not an error."""
    candidate_or_404(db, user, candidate_id)
    db.query(CandidateTag).filter(
        CandidateTag.candidate_id == candidate_id, CandidateTag.tag == tag
    ).delete(synchronize_session=False)
    db.commit()
    return CandidateTagsResponse(candidate_id=candidate_id, tags=_tags(db, candidate_id))


@router.get("/tags", response_model=List[TagCount])
def list_tags(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> List[TagCount]:
    """Every tag in use with how many candidates carry it, most used first."""
    count = func.count(CandidateTag.candidate_id)
    query = db.query(CandidateTag.tag, count).group_by(CandidateTag.tag)
    visible = visible_candidate_ids(db, user)
    if visible is not None:
        if not visible:
            return []
        query = query.filter(CandidateTag.candidate_id.in_(visible))
    return [TagCount(tag=tag, count=n) for tag, n in query.order_by(count.desc(), CandidateTag.tag).all()]
