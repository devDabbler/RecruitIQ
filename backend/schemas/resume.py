from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Helper Schemas for ParsedResumeData ---

class PersonalInfo(BaseModel):
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None

class Skill(BaseModel):
    name: str
    category: Optional[str] = None
    level: Optional[str] = None

class Education(BaseModel):
    institution: str
    degree: str
    major: Optional[str] = None
    gpa: Optional[str] = None
    location: Optional[str] = None
    date_range: Optional[str] = None
    start_date: Optional[str] = None # Consider parsing to date
    end_date: Optional[str] = None   # Consider parsing to date

class Experience(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    date_range: str
    start_date: Optional[str] = None # Consider parsing to date
    end_date: Optional[str] = None   # Consider parsing to date or 'Present'
    description: Optional[str] = None
    achievements: Optional[List[str]] = []
    technologies: Optional[List[str]] = []

class Project(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: Optional[List[str]] = []
    date_range: Optional[str] = None
    link: Optional[str] = None

class Certification(BaseModel):
    name: str
    issuing_organization: Optional[str] = None
    date_issued: Optional[str] = None # Consider parsing to date
    credential_id: Optional[str] = None

class Language(BaseModel):
    language: str
    proficiency: Optional[str] = None

class Publication(BaseModel):
    title: str
    publisher: Optional[str] = None
    date: Optional[str] = None
    link: Optional[str] = None


# --- Main Resume Schemas ---

class ParsedResumeData(BaseModel):
    personal_info: Optional[PersonalInfo] = Field(default_factory=PersonalInfo)
    summary: Optional[str] = None
    skills: Optional[List[Skill]] = Field(default_factory=list)
    education: Optional[List[Education]] = Field(default_factory=list)
    experience: Optional[List[Experience]] = Field(default_factory=list)
    projects: Optional[List[Project]] = Field(default_factory=list)
    certifications: Optional[List[Certification]] = Field(default_factory=list)
    languages: Optional[List[Language]] = Field(default_factory=list)
    publications: Optional[List[Publication]] = Field(default_factory=list)
    volunteer_experience: Optional[List[Experience]] = Field(default_factory=list) # Reusing Experience schema
    raw_text: Optional[str] = None # Store the original raw text
    source_format: Optional[str] = None # e.g., 'pdf', 'docx'
    parsing_model_version: Optional[str] = None # Model used for parsing

class ResumeCreateSchema(BaseModel):
    user_id: int # Assuming it's linked to a user
    file_name: Optional[str] = None
    parsed_data: Optional[ParsedResumeData] = None # Can be created with or without pre-parsed data
    raw_text: Optional[str] = None # If created from raw text directly

class ResumeUpdateSchema(BaseModel):
    file_name: Optional[str] = None
    parsed_data: Optional[ParsedResumeData] = None
    raw_text: Optional[str] = None
    is_primary: Optional[bool] = None # If user can have multiple resumes
    # Add any other fields that can be updated

class ResumeSchema(BaseModel):
    id: int
    user_id: int
    file_name: Optional[str] = None
    upload_date: datetime
    last_updated: datetime
    parsed_data: Optional[ParsedResumeData] = None
    raw_text: Optional[str] = None
    is_primary: bool = False

    class Config:
        orm_mode = True
        from_attributes = True


class ResumeParseResponse(BaseModel):
    message: str
    file_name: Optional[str] = None
    parsed_data: Optional[ParsedResumeData] = None
    error: Optional[str] = None

class ResumeScoreSchema(BaseModel):
    resume_id: int
    job_role_id: int # Assuming you have job roles
    score: float = Field(..., ge=0, le=100) # Score between 0 and 100
    match_summary: Optional[str] = None
    detailed_breakdown: Optional[Dict[str, Any]] = None # e.g., {"skills_match": 80, "experience_match": 70}
    score_date: datetime = Field(default_factory=datetime.utcnow)

class ResumeEvaluationResultSchema(BaseModel):
    resume_id: int
    job_role_id: Optional[int] = None # Could be a general evaluation or against a specific role
    evaluation_summary: str
    strengths: Optional[List[str]] = Field(default_factory=list)
    areas_for_improvement: Optional[List[str]] = Field(default_factory=list)
    fit_score: Optional[float] = None # Overall fit score if applicable
    detailed_feedback: Optional[Dict[str, Any]] = None
    evaluation_date: datetime = Field(default_factory=datetime.utcnow)
    evaluator: Optional[str] = "AI Model" # Could be human or AI

class ResumeAnalysisResult(BaseModel):
    resume_id: Optional[int] = None # If an existing resume is analyzed
    parsed_data: ParsedResumeData
    evaluation: Optional[ResumeEvaluationResultSchema] = None
    score: Optional[ResumeScoreSchema] = None # If scored against a job
    warnings: Optional[List[str]] = Field(default_factory=list) # e.g., missing critical sections
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow) 