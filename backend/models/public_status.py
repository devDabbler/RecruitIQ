"""Shapes for the candidate-facing status page (ATS Phase E).

PublicStatus is an allowlist. Adding a field here publishes it to anyone
holding a status link, so test_status_links pins the exact key set.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PublicStage(BaseModel):
    name: str
    description: Optional[str] = None
    # done, current, upcoming, closed
    state: str


class PublicStatus(BaseModel):
    first_name: Optional[str] = None
    job_title: str
    department: Optional[str] = None
    # In progress, Hired, Closed
    status: str
    stages: List[PublicStage]


class StatusLinkOut(BaseModel):
    active: bool
    # Relative path, e.g. /c/<token>. The web app builds the absolute URL.
    path: Optional[str] = None
    created_at: Optional[datetime] = None
