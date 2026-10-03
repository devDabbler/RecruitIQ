"""Candidate status links (ATS Phase E).

`GET /api/public/status/{token}` is the only unauthenticated route that
returns data about one person, so it returns the allowlisted PublicStatus
and nothing else. Unknown, replaced, and revoked tokens get the same 404
body. Plain `def` handlers (sync ORM; CLAUDE.md sharp edge).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.models import JobApplication, User
from ..models.public_status import PublicStatus, StatusLinkOut
from ..services import status_link_service as links
from ..utils.auth import get_optional_user
from ..utils.database import get_db
from ..utils.permissions import PIPELINE_MOVE, require
from .application_access import visible_application_or_404

router = APIRouter()

INACTIVE = "This status link is not active."


def _link_out(application: JobApplication) -> StatusLinkOut:
    if not application.public_token:
        return StatusLinkOut(active=False)
    return StatusLinkOut(
        active=True,
        path=f"/c/{application.public_token}",
        created_at=application.public_token_created_at,
    )


@router.get("/public/status/{token}", response_model=PublicStatus)
def get_public_status(token: str, db: Session = Depends(get_db)) -> PublicStatus:
    """What a candidate sees at their status link. No authentication."""
    application = links.find_by_token(db, token)
    if application is None:
        raise HTTPException(status_code=404, detail=INACTIVE)
    view = links.public_view(db, application)
    db.commit()  # public_view may lazily create stage rows
    return view


@router.get("/applications/{application_id}/candidate-view", response_model=PublicStatus)
def get_candidate_view(
    application_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> PublicStatus:
    """The same page a status link shows, for staff and the demo to preview."""
    application = visible_application_or_404(db, application_id, user)
    view = links.public_view(db, application)
    db.commit()
    return view


@router.get("/applications/{application_id}/status-link", response_model=StatusLinkOut)
def get_status_link(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require(PIPELINE_MOVE)),
) -> StatusLinkOut:
    return _link_out(visible_application_or_404(db, application_id, user))


@router.post("/applications/{application_id}/status-link", response_model=StatusLinkOut)
def create_status_link(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require(PIPELINE_MOVE)),
) -> StatusLinkOut:
    """Create the link, or replace it (the old one stops working immediately)."""
    application = visible_application_or_404(db, application_id, user)
    links.issue_link(db, application)
    db.commit()
    return _link_out(application)


@router.delete("/applications/{application_id}/status-link", response_model=StatusLinkOut)
def revoke_status_link(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require(PIPELINE_MOVE)),
) -> StatusLinkOut:
    application = visible_application_or_404(db, application_id, user)
    links.revoke_link(db, application)
    db.commit()
    return _link_out(application)
