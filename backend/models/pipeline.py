"""Request and response shapes for the pipeline router (ATS Phase A)."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class StageOut(BaseModel):
    id: int
    key: str
    name: str
    kind: str
    description: Optional[str] = None
    position: int
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class ApplicationCard(BaseModel):
    """One candidate chip on the board."""
    application_id: int
    candidate_id: str
    candidate_name: str
    current_position: Optional[str] = None
    entered_at: Optional[datetime] = None


class BoardColumn(BaseModel):
    stage_key: str
    stage_name: str
    applications: List[ApplicationCard]


class JobPipelineResponse(BaseModel):
    job_id: int
    stages: List[StageOut]
    columns: List[BoardColumn]
    outcomes: Dict[str, int]


class StageUpdate(BaseModel):
    key: str
    enabled: bool
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None


class PipelineUpdateRequest(BaseModel):
    stages: List[StageUpdate]


class ApplicationStageOut(BaseModel):
    key: str
    name: str
    kind: str
    description: Optional[str] = None
    enabled: bool
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    note: Optional[str] = None


class ApplicationDetail(BaseModel):
    id: int
    job_id: int
    job_title: str
    candidate_id: str
    candidate_name: str
    status: str
    current_stage_key: Optional[str] = None
    current_stage_name: Optional[str] = None
    applied_at: Optional[datetime] = None
    stages: List[ApplicationStageOut]


class TransitionRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)
