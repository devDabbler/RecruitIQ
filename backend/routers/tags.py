"""Tags on candidates (ATS Phase C).

Writes are gated by `ROUTE_PERMISSIONS` (PIPELINE_MOVE); reads by
`visible_candidate_ids` through `notes.candidate_or_404`.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.intake import CandidateTagsResponse, TagCount, TagCreate
from ..models.models import CandidateTag, User
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
            raise HTTPException(
                status_code=409,
                detail=f"A candidate can carry at most {MAX_TAGS_PER_CANDIDATE} tags. Remove one first.",
            )
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
