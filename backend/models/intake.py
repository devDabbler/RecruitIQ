"""Request and response shapes for notes and tags (ATS Phase C)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    # Both null: a note about the person. application_id alone: about that
    # application in general. Both set: about one stage of it.
    application_id: Optional[int] = None
    stage_key: Optional[str] = None


class NoteOut(BaseModel):
    id: int
    candidate_id: str
    body: str
    created_at: datetime
    # Null only for text imported from the old candidates.notes column.
    author_name: Optional[str] = None
    application_id: Optional[int] = None
    job_title: Optional[str] = None
    stage_name: Optional[str] = None


class TagCreate(BaseModel):
    tag: str = Field(max_length=80)


class CandidateTagsResponse(BaseModel):
    candidate_id: str
    tags: List[str]


class TagCount(BaseModel):
    tag: str
    count: int


class BulkTagRequest(BaseModel):
    """Track 2 Phase 5: one tag for many candidates."""
    candidate_ids: List[str] = Field(min_length=1, max_length=100)
    tag: str = Field(max_length=80)


class BulkTagItem(BaseModel):
    candidate_id: str
    ok: bool
    candidate_name: Optional[str] = None
    detail: Optional[str] = None


class BulkTagResponse(BaseModel):
    tag: str
    succeeded: int
    failed: int
    results: List[BulkTagItem]
