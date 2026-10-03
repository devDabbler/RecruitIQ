"""Candidate status links (ATS Phase E, spec 2026-10-03 section 8).

A link is a random token on the application. Holding it shows the
candidate's first name, the job, and the stage timeline, and nothing else.
Regenerating replaces the token (the old link stops working at once);
revoking clears it. Unknown, replaced, and revoked tokens are all the same
404 to the caller.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.models import Candidate, Job, JobApplication
from backend.models.public_status import PublicStage, PublicStatus
from backend.services import pipeline_service as ps

# 24 random bytes -> 32 URL-safe characters, which fits the 36-character
# column and is far beyond guessing range.
TOKEN_BYTES = 24
MAX_TOKEN_LENGTH = 64

PUBLIC_APPLICATION_STATUS = {
    ps.APP_ACTIVE: "In progress",
    ps.APP_HIRED: "Hired",
    ps.APP_REJECTED: "Closed",
    ps.APP_DECLINED: "Closed",
    ps.APP_WITHDRAWN: "Closed",
}

_PUBLIC_STAGE_STATE = {
    ps.PASSED: "done",
    ps.IN_PROGRESS: "current",
    ps.PENDING: "upcoming",
    ps.FAILED: "closed",
}


def issue_link(db: Session, application: JobApplication) -> str:
    """Create or replace the application's link and return the new token."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    application.public_token = token
    application.public_token_created_at = datetime.utcnow()
    db.flush()
    return token


def revoke_link(db: Session, application: JobApplication) -> None:
    application.public_token = None
    application.public_token_created_at = None
    db.flush()


def find_by_token(db: Session, token: str) -> Optional[JobApplication]:
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    return db.query(JobApplication).filter(JobApplication.public_token == token).first()


def public_view(db: Session, application: JobApplication) -> PublicStatus:
    """The candidate-facing view, built only from allowlisted fields."""
    rows = ps.ensure_application_stages(db, application)
    job = db.get(Job, application.job_id)
    candidate = db.get(Candidate, application.candidate_id)

    stages = []
    for row in rows:
        stage = row.stage
        if row.status == ps.SKIPPED:
            continue
        if stage.kind == ps.OUTCOME and row.status != ps.PASSED:
            continue
        if row.status == ps.PENDING and not stage.enabled:
            continue
        stages.append(
            PublicStage(
                name=stage.name,
                description=stage.description,
                state=_PUBLIC_STAGE_STATE[row.status],
            )
        )

    first_name = (candidate.first_name or "").strip() if candidate else ""
    return PublicStatus(
        first_name=first_name or None,
        job_title=(job.title if job else "") or "",
        department=job.department if job else None,
        status=PUBLIC_APPLICATION_STATUS.get(application.status, "In progress"),
        stages=stages,
    )
