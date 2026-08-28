from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    ON_HOLD = "on_hold"
    FILLED = "filled"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


class LocationType(str, Enum):
    ON_SITE = "on_site"
    REMOTE = "remote"
    HYBRID = "hybrid"


class ExperienceLevel(str, Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


class JobCreateUpdate(BaseModel):
    """Schema for creating or updating a job posting. 'skills' is a list of required skills for the job."""
    title: str
    department: str
    job_overview: str
    required_qualifications: str
    location: Optional[str] = None
    location_type: LocationType = LocationType.ON_SITE
    job_type: JobType = JobType.FULL_TIME
    experience_level: ExperienceLevel = ExperienceLevel.MID
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    status: JobStatus = JobStatus.DRAFT
    hiring_manager: Optional[str] = None
    recruiter: Optional[str] = None
    application_deadline: Optional[datetime] = None
    start_date: Optional[datetime] = None
    job_metadata: Dict[str, Any] = Field(default_factory=dict)
    skills: List[str] = Field(default_factory=list)


class JobResponse(BaseModel):
    """Schema for job response with all details. 'skills' is a list of required skills for the job."""
    id: int
    title: str
    department: str
    job_overview: str
    required_qualifications: str
    location: Optional[str] = None
    location_type: str
    job_type: str
    experience_level: str
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    status: str
    hiring_manager: Optional[str] = None
    recruiter: Optional[str] = None
    application_deadline: Optional[datetime] = None
    start_date: Optional[datetime] = None
    views: int = 0
    applications: int = 0
    created_at: datetime
    updated_at: datetime
    job_metadata: Dict[str, Any] = Field(default_factory=dict)
    skills: List[str] = Field(default_factory=list)

    # jobs.job_metadata, .views and .applications are all nullable columns, but
    # a field default only applies when the key is *absent* — an explicit None
    # still fails validation. Any job row carrying a NULL in one of these
    # therefore 500'd the whole listing, not just its own entry. Coerce instead.
    @field_validator("job_metadata", "skills", "views", "applications", mode="before")
    @classmethod
    def _null_means_empty(cls, value, info):
        if value is not None:
            return value
        return {"job_metadata": {}, "skills": [], "views": 0, "applications": 0}[
            info.field_name
        ]

    model_config = {"from_attributes": True}


class JobSearchQuery(BaseModel):
    """Schema for job search query parameters."""
    keyword: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    location_type: Optional[LocationType] = None
    job_type: Optional[JobType] = None
    experience_level: Optional[ExperienceLevel] = None
    status: Optional[JobStatus] = None
    skills: Optional[List[str]] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    sort_by: Optional[str] = "created_at"
    sort_order: Optional[str] = "desc"
    page: int = 1
    page_size: int = 10


class JobSearchResponse(BaseModel):
    """Schema for paginated job search results."""
    total: int
    page: int
    page_size: int
    results: List[JobResponse]


class JobMetrics(BaseModel):
    """Schema for job posting performance metrics."""
    views: int = 0
    applications: int = 0
    interviews: int = 0
    offers: int = 0
    hires: int = 0
    average_time_to_fill: Optional[int] = None  # days
    cost_per_hire: Optional[float] = None
    conversion_rates: Dict[str, float] = Field(default_factory=dict)
    source_breakdown: Dict[str, int] = Field(default_factory=dict)
