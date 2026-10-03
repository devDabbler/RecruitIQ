"""Request and response shapes for interviews and feedback (ATS Phase B)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Recommendation = Literal["strong_hire", "hire", "no_hire", "strong_no_hire"]
InterviewState = Literal["upcoming", "waiting", "submitted", "skipped"]


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    recommendation: Recommendation
    notes: str = Field(default="", max_length=5000)


class FeedbackOut(BaseModel):
    rating: int
    recommendation: str
    notes: Optional[str] = None
    submitted_at: datetime


class InterviewOut(BaseModel):
    id: int
    application_id: int
    stage_key: str
    stage_name: str
    stage_status: str
    state: InterviewState
    interviewer_id: str
    interviewer_name: str
    assignment_source: str
    feedback: Optional[FeedbackOut] = None
    # True when feedback exists but this viewer may not read it yet.
    feedback_hidden: bool = False


class InterviewListItem(InterviewOut):
    candidate_id: str
    candidate_name: str
    job_id: int
    job_title: str
    score_visible: bool


class InterviewListResponse(BaseModel):
    items: List[InterviewListItem]


class AssignRequest(BaseModel):
    stage_key: str = Field(min_length=1, max_length=50)
    interviewer_id: str = Field(min_length=1, max_length=36)


class TeamMemberBrief(BaseModel):
    id: str
    name: str
    role: str


class StageDefaults(BaseModel):
    stage_key: str
    stage_name: str
    users: List[TeamMemberBrief]


class DefaultInterviewersResponse(BaseModel):
    job_id: int
    stages: List[StageDefaults]


class DefaultInterviewersRequest(BaseModel):
    user_ids: List[str] = Field(default_factory=list, max_length=20)
