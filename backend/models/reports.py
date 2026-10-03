"""Response shapes for the reports router (ATS Phase D)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FunnelRow(BaseModel):
    key: str
    name: str
    position: int
    ever_reached: int
    currently_here: int
    share_of_applicants: float


class StageTiming(BaseModel):
    key: str
    name: str
    position: int
    median_days: Optional[float] = None
    completed: int


class WaitingApplication(BaseModel):
    application_id: int
    candidate_id: str
    candidate_name: str
    job_id: int
    job_title: str
    stage_key: str
    stage_name: str
    since: datetime
    days_waiting: int


class PendingFeedbackRow(BaseModel):
    interview_id: int
    interviewer_name: Optional[str] = None
    application_id: int
    candidate_id: str
    candidate_name: str
    job_id: int
    job_title: str
    stage_name: str
    days_pending: int


class SourceRow(BaseModel):
    source: str
    applications: int
    hired: int


class QuarterOutcomes(BaseModel):
    label: str
    start: datetime
    end: datetime
    hires: int
    rejections: int
    offers_declined: int


class ActivityEvent(BaseModel):
    at: datetime
    kind: str
    candidate_id: str
    candidate_name: str
    job_id: int
    job_title: str
    stage_name: Optional[str] = None
    actor_name: Optional[str] = None


class DashboardResponse(BaseModel):
    generated_at: datetime
    total_applications: int
    interviewing_or_later: int
    funnel: List[FunnelRow]
    no_movement: List[WaitingApplication]
    no_movement_total: int
    pending_feedback: List[PendingFeedbackRow]
    activity: List[ActivityEvent]


class ReportsResponse(BaseModel):
    generated_at: datetime
    job_id: Optional[int] = None
    job_title: Optional[str] = None
    total_applications: int
    funnel: List[FunnelRow]
    time_in_stage: List[StageTiming]
    no_movement: List[WaitingApplication]
    no_movement_total: int
    source_mix: List[SourceRow]
    quarters: List[QuarterOutcomes]
