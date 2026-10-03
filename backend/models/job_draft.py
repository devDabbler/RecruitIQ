"""Request and response shapes for AI job description drafts (ATS Phase E)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class JobDraftRequest(BaseModel):
    """Only the structured job fields. There is deliberately no free-text field."""
    title: str = Field(min_length=1, max_length=255)
    department: Optional[str] = Field(default=None, max_length=100)
    experience_level: Optional[str] = Field(default=None, max_length=50)
    location_type: Optional[str] = Field(default=None, max_length=50)
    skills: List[str] = Field(default_factory=list, max_length=30)


class JobDescriptionDraft(BaseModel):
    job_overview: str
    required_qualifications: str
