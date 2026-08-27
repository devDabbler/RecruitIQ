print('[DEBUG] resume.py: top of file')
print('[DEBUG] resume.py: importing typing')
from typing import Dict, List, Optional, Union, Any
print('[DEBUG] resume.py: importing pydantic')
from pydantic import BaseModel, Field
print('[DEBUG] resume.py: importing datetime')
from datetime import datetime

class Section(BaseModel):
    """A section of a resume with its title and content."""
    title: str
    content: str
    markdown_content: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class PersonalInfo(BaseModel):
    """Personal information from a resume."""
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    website: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    twitter: Optional[str] = None

class Education(BaseModel):
    """Educational background information."""
    degree: str
    institution: str
    location: Optional[str] = None
    date_range: Optional[str] = None
    start_date: Optional[Union[datetime, str, None]] = None
    end_date: Optional[Union[datetime, str, None]] = None
    gpa: Optional[Union[float, None]] = None
    description: Optional[str] = None
    achievements: List[str] = Field(default_factory=list)
    honors: List[str] = Field(default_factory=list)
    courses: List[str] = Field(default_factory=list)
    
    model_config = {
        "arbitrary_types_allowed": True
    }

class Experience(BaseModel):
    """Work experience information."""
    title: str
    company: str
    location: Optional[str] = None
    date_range: Optional[str] = None
    start_date: Optional[Union[datetime, str, None]] = None
    end_date: Optional[Union[datetime, str, None]] = None
    description: str
    achievements: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    skills_demonstrated: List[str] = Field(default_factory=list)
    employment_type: Optional[str] = None
    seniority_level: Optional[str] = None
    
    model_config = {
        "arbitrary_types_allowed": True
    }

class Project(BaseModel):
    """Project information."""
    name: str
    description: str
    technologies: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    date_range: Optional[str] = None
    start_date: Optional[Union[datetime, str, None]] = None
    end_date: Optional[Union[datetime, str, None]] = None
    achievements: List[str] = Field(default_factory=list)
    role: Optional[str] = None
    
    model_config = {
        "arbitrary_types_allowed": True
    }

class Certification(BaseModel):
    """Certification information."""
    name: str
    issuer: str
    date: Optional[str] = None
    issued_date: Optional[datetime] = None
    expires: Optional[str] = None
    expiry_date: Optional[datetime] = None
    credential_id: Optional[str] = None
    url: Optional[str] = None

class Language(BaseModel):
    """Language proficiency information."""
    name: str = Field(alias="language")
    proficiency: str
    certification: Optional[str] = None
    
    model_config = {
        "populate_by_name": True
    }

class Skill(BaseModel):
    """Detailed skill information."""
    name: str
    category: Optional[str] = None
    level: Optional[str] = None
    years_experience: Optional[float] = None
    last_used: Optional[datetime] = None

class Publication(BaseModel):
    """Publication information."""
    title: str
    publisher: Optional[str] = None
    date: Optional[Union[datetime, str, None]] = None
    url: Optional[str] = None
    description: Optional[str] = None
    
    model_config = {
        "arbitrary_types_allowed": True
    }

class Volunteer(BaseModel):
    """Volunteer experience information."""
    organization: str
    role: Optional[str] = None
    start_date: Optional[Union[datetime, str, None]] = None
    end_date: Optional[Union[datetime, str, None]] = None
    description: Optional[str] = None
    
    model_config = {
        "arbitrary_types_allowed": True
    }

class ResumeData(BaseModel):
    """Complete structured resume data."""
    file_id: str
    file_name: str
    content_type: str
    full_text: str
    markdown_text: Optional[str] = None
    sections: List[Section]
    personal_info: PersonalInfo
    summary: Optional[str] = None
    skills: List[Union[Skill, str]] = Field(default_factory=list)
    skill_categories: Optional[Dict[str, List[str]]] = None
    education: List[Education] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    military: List[Experience] = Field(default_factory=list)  # Added dedicated field for military experience
    projects: List[Project] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    publications: List[Publication] = Field(default_factory=list)
    volunteer: List[Volunteer] = Field(default_factory=list)
    raw_entities: Dict = Field(default_factory=dict)
    embeddings: Dict = Field(default_factory=dict)
    metadata: Dict = Field(default_factory=dict)
    # AI prediction fields
    ai_score: Optional[int] = None
    recommendation: Optional[Dict[str, Any]] = None
    salary_range: Optional[Dict[str, Any]] = None
    skill_gaps: Optional[List[str]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "arbitrary_types_allowed": True
    }
