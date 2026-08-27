from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict, validator
from datetime import datetime
from enum import Enum


class CandidateStatus(str, Enum):
    ACTIVE = "active"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    ON_HOLD = "on_hold"


class CandidateSource(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    COMPANY_WEBSITE = "company_website"
    REFERRAL = "referral"
    AGENCY = "agency"
    JOB_BOARD = "job_board"
    DIRECT_APPLICATION = "direct_application"
    OTHER = "other"


class CandidateCreate(BaseModel):
    """Schema for creating a new candidate."""
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None
    source: Optional[CandidateSource] = None
    status: Union[CandidateStatus, str] = CandidateStatus.ACTIVE
    position_applied: Optional[str] = None
    job_id: Optional[int] = None
    notes: Optional[str] = None


class CandidateUpdate(BaseModel):
    """Schema for updating an existing candidate."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None
    source: Optional[CandidateSource] = None
    status: Optional[CandidateStatus] = None
    position_applied: Optional[str] = None
    job_id: Optional[int] = None
    notes: Optional[str] = None


class CandidateSkill(BaseModel):
    """Schema for a candidate skill."""
    skill_name: str
    years_experience: Optional[int] = None
    proficiency_level: Optional[str] = None


class CandidateNote(BaseModel):
    """Schema for a note about a candidate."""
    content: str
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CandidateInteraction(BaseModel):
    """Schema for tracking interactions with a candidate."""
    interaction_type: str  # email, phone, interview, etc.
    date: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    next_steps: Optional[str] = None
    conducted_by: Optional[str] = None


class CandidateResponse(BaseModel):
    """Schema for candidate response with all details."""
    id: str  # changed from int to str
    first_name: Optional[str] = None  # Made optional to handle NULL values
    last_name: Optional[str] = None   # Made optional to handle NULL values
    email: Optional[str] = None  # Changed from EmailStr to str to handle empty strings
    phone: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = "active"  # Made optional with default value
    position_applied: Optional[str] = None
    job_id: Optional[int] = None
    notes: Optional[str] = None
    skills: Optional[List[str]] = None  # changed from str to list of strings
    current_position: Optional[str] = None
    current_company: Optional[str] = None
    interactions: List[CandidateInteraction] = Field(default_factory=list)
    candidate_notes: List[CandidateNote] = Field(default_factory=list)
    # Add resume data fields
    education: List[Dict[str, Any]] = Field(default_factory=list)
    work_experience: List[Dict[str, Any]] = Field(default_factory=list)
    parsed_data: Optional[Dict[str, Any]] = None
    resume_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    @validator('email', pre=True)
    def validate_email(cls, v):
        """Handle empty string emails by converting to None."""
        if v == '' or v is None:
            return None
        # Basic email validation for non-empty strings
        if '@' not in str(v):
            return None
        return v
    
    @validator('first_name', 'last_name', pre=True)
    def validate_names(cls, v):
        """Handle None values by providing default placeholder."""
        if v is None:
            return ""
        return v
    
    @validator('status', pre=True)
    def validate_status(cls, v):
        """Handle None status by providing default value."""
        if v is None:
            return "active"
        return v
    
    model_config = ConfigDict(from_attributes=True)



class CandidateSearchResponse(BaseModel):
    """Schema for paginated candidate search results."""
    total: int
    page: int
    page_size: int
    results: List[CandidateResponse]
    
    model_config = ConfigDict(from_attributes=True)


# Note: The Candidate SQLAlchemy model is defined in models.py to avoid conflicts
# This file contains only Pydantic schemas for API requests/responses
