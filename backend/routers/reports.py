"""Reports and dashboard numbers (ATS Phase D, spec 2026-10-03 section 8).

Reads only, so nothing here needs a ROUTE_PERMISSIONS entry. Plain `def`
handlers: they do sync ORM work and must not run on the event loop
(CLAUDE.md sharp edge).

Who sees what:
- The dashboard numbers are for every viewer, anonymous and demo included,
  narrowed to the candidates that viewer may see. An interviewer's
  dashboard counts only the people they are assigned to.
- The Reports summary needs REPORTS_VIEW (admin, hiring manager, hiring
  team) or the read-only demo role. The demo is let through explicitly
  because a visitor from the portfolio link must be able to see every
  screen; it is synthetic data and the summary carries no contact details
  and no match scores.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..models.models import Job, User
from ..models.reports import DashboardResponse, ReportsResponse
from ..services import reports_service as rs
from ..services.access_service import visible_candidate_ids
from ..utils.auth import ROLE_DEMO, get_current_user, get_optional_user
from ..utils.database import get_db
from ..utils.permissions import REPORTS_VIEW, can

router = APIRouter(prefix="/reports")


def reports_reader(user: User = Depends(get_current_user)) -> User:
    if user.role == ROLE_DEMO or can(user.role, REPORTS_VIEW):
        return user
    raise HTTPException(status_code=403, detail="Reports are not available for your role.")


def _visible(db: Session, user: Optional[User]):
    return None if user is None else visible_candidate_ids(db, user)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> DashboardResponse:
    """Funnel, attention list, and activity for the dashboard."""
    scope = rs.Scope.of(candidate_ids=_visible(db, user))
    return DashboardResponse(**rs.dashboard(db, scope, datetime.utcnow(), viewer=user))


@router.get("/summary", response_model=ReportsResponse)
def get_summary(
    job_id: Optional[int] = Query(default=None, description="Limit every number to one job"),
    db: Session = Depends(get_db),
    user: User = Depends(reports_reader),
) -> ReportsResponse:
    """Everything on the Reports page, for all jobs or one."""
    job_title = None
    if job_id is not None:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        job_title = job.title
    scope = rs.Scope.of(job_id=job_id, candidate_ids=_visible(db, user))
    return ReportsResponse(job_title=job_title, **rs.reports(db, scope, datetime.utcnow()))
