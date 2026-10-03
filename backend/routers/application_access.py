"""Load an application the caller is allowed to see, or 404 (ATS Phase E).

Interviewers only see candidates they are assigned to (Phase B,
access_service). A route that serves one application must hide the rest
behind the same 404 an unknown id gets, so the existence of an application
is not itself a leak.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.models.models import ApplicationStage, JobApplication, User
from backend.services import access_service


def visible_application_or_404(
    db: Session, application_id: int, user: Optional[User]
) -> JobApplication:
    application = (
        db.query(JobApplication)
        .options(joinedload(JobApplication.stages).joinedload(ApplicationStage.stage))
        .filter(JobApplication.id == application_id)
        .first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if user is not None:
        visible = access_service.visible_candidate_ids(db, user)
        if visible is not None and application.candidate_id not in visible:
            raise HTTPException(status_code=404, detail="Application not found")
    return application
