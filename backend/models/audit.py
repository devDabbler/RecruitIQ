"""Response shapes for the audit log (pilot plan Track 1 #3)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: int
    occurred_at: datetime
    actor_id: Optional[str] = None
    # From the users table when the account still exists.
    actor_email: Optional[str] = None
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    subject_type: str
    subject_id: Optional[str] = None
    candidate_id: Optional[str] = None
    endpoint: str
    detail: Optional[str] = None
    fields: Optional[List[str]] = None
    status_code: int


class AuditEventPage(BaseModel):
    events: List[AuditEventOut]
    # Pass as `before_id` to fetch the next, older page. Null on the last page.
    next_before_id: Optional[int] = None
