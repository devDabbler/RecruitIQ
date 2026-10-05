"""Read the audit log (pilot plan Track 1 #3). Administrators only.

Newest first, paged by id. The filters cover the questions a privacy or
security reviewer asks: everything that happened to one person
(`candidate_id`), everything one account did (`actor_id`), and every export
or deletion (`action`). Plain `def`: sync ORM work stays off the event loop.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..models.audit import AuditEventOut, AuditEventPage
from ..models.models import AuditEvent, User
from ..services.audit_service import ACTIONS
from ..utils.database import get_db
from ..utils.permissions import AUDIT_VIEW, require

router = APIRouter()


@router.get("/audit-events", response_model=AuditEventPage)
def list_audit_events(
    candidate_id: Optional[str] = Query(None, max_length=36),
    actor_id: Optional[str] = Query(None, max_length=36),
    action: Optional[str] = Query(None),
    subject_type: Optional[str] = Query(None, max_length=32),
    before_id: Optional[int] = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: User = Depends(require(AUDIT_VIEW)),
) -> AuditEventPage:
    if action is not None and action not in ACTIONS:
        raise HTTPException(status_code=422, detail=f"action must be one of: {', '.join(ACTIONS)}")

    query = db.query(AuditEvent, User).outerjoin(User, User.id == AuditEvent.actor_id)
    if candidate_id:
        query = query.filter(AuditEvent.candidate_id == candidate_id)
    if actor_id:
        query = query.filter(AuditEvent.actor_id == actor_id)
    if action:
        query = query.filter(AuditEvent.action == action)
    if subject_type:
        query = query.filter(AuditEvent.subject_type == subject_type)
    if before_id:
        query = query.filter(AuditEvent.id < before_id)
    rows = query.order_by(AuditEvent.id.desc()).limit(limit + 1).all()

    events = [
        AuditEventOut(
            id=event.id,
            occurred_at=event.occurred_at,
            actor_id=event.actor_id,
            actor_email=actor.email if actor else None,
            actor_name=actor.name if actor else None,
            actor_role=event.actor_role,
            action=event.action,
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            candidate_id=event.candidate_id,
            endpoint=event.endpoint,
            detail=event.detail,
            fields=event.fields,
            status_code=event.status_code,
        )
        for event, actor in rows[:limit]
    ]
    next_before_id = events[-1].id if len(rows) > limit else None
    return AuditEventPage(events=events, next_before_id=next_before_id)
