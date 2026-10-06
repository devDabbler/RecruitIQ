"""Request and response shapes for the departments router (Track 2 Phase 3)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DepartmentOut(BaseModel):
    id: int
    name: str
    active: bool
    # Jobs that name this department; shown in the admin list.
    job_count: int = 0


class DepartmentListResponse(BaseModel):
    departments: List[DepartmentOut]


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    active: Optional[bool] = None


class DepartmentUpdateResponse(BaseModel):
    department: DepartmentOut
    # How many jobs a rename moved to the new name.
    jobs_renamed: int = 0
