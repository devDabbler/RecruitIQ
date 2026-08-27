import uuid
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Table, UniqueConstraint, event, Float, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.utils.database import Base
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any, Union
from datetime import date

# CandidateSkill model
class CandidateSkill(Base):
    """Model for candidate skills (many-to-many with skill level information)."""
    __tablename__ = "candidate_skills"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    skill_name = Column(String(255), nullable=False)
    proficiency = Column(String(50), nullable=True)
    years_of_experience = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('candidate_id', 'skill_name', name='unique_candidate_skill'),
    )

    candidate = relationship("Candidate", back_populates="skills")

    def __repr__(self):
        return f"<CandidateSkill(candidate_id={self.candidate_id}, skill_name='{self.skill_name}', proficiency='{self.proficiency}')>"

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    first_name = Column(String(100), index=True)  # Add index for name searches
    last_name = Column(String(100), index=True)   # Add index for name searches
    email = Column(String(255), unique=True, index=True)
    phone = Column(String(20))
    location = Column(String(255), nullable=True)
    headline = Column(String(255), nullable=True)
    source = Column(String(50), nullable=True)
    status = Column(String(50), default="active", index=True)  # Add index for status filtering
    position_applied = Column(String(255), nullable=True, index=True)  # Add index for position searches
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    notes = Column(Text, nullable=True)
    current_position = Column(String(255), nullable=True)
    current_company = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # Add index for sorting
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    skills = relationship("CandidateSkill", back_populates="candidate", cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="candidate")
    candidate_applications = relationship("JobApplication", back_populates="candidate")
    saved_jobs = relationship("SavedJob", back_populates="candidate")
    pitches = relationship("CandidatePitch", back_populates="candidate")
    
    # Add composite indexes for common query patterns
    __table_args__ = (
        Index('idx_candidate_name_search', 'first_name', 'last_name'),  # For name searches
        Index('idx_candidate_status_position', 'status', 'position_applied'),  # For status + position filtering
        Index('idx_candidate_created_status', 'created_at', 'status'),  # For sorting by date with status
    )

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"))
    file_id = Column(String(255), unique=True, index=True)
    file_path = Column(String(255))
    file_name = Column(String(255))
    file_type = Column(String(50))
    parsed_content = Column(Text)
    parsed_data = Column(JSON, nullable=True)
    vector_embedding = Column(JSON)
    parser_version = Column(String(50), nullable=True)  # Track parser version
    validation_status = Column(String(50), default='pending')  # Track parsing confidence
    validation_score = Column(Float, nullable=True)  # Store parsing confidence score
    last_synced_to_neo4j = Column(DateTime, nullable=True)  # Track Neo4j sync
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Create indexes on JSON fields for faster querying
    __table_args__ = (
        Index('idx_parsed_data_email', 'parsed_data', postgresql_using='gin'),
        Index('idx_parsed_data_skills', 'parsed_data', postgresql_using='gin'),
    )

    candidate = relationship("Candidate", back_populates="resumes")
    
    @property
    def text(self):
        """Property to access resume text content for compatibility with search functions."""
        return self.parsed_content

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    department = Column(String(100))
    job_overview = Column(Text)
    required_qualifications = Column(Text)
    location = Column(String(255), nullable=True)
    location_type = Column(String(50))
    job_type = Column(String(50))
    experience_level = Column(String(50))
    min_salary = Column(Integer, nullable=True)
    max_salary = Column(Integer, nullable=True)
    hiring_manager = Column(String(255), nullable=True)
    recruiter = Column(String(255), nullable=True)
    application_deadline = Column(DateTime, nullable=True)
    start_date = Column(DateTime, nullable=True)
    job_metadata = Column(JSON, nullable=True)
    status = Column(String(50), default="open")
    skills = Column(String, nullable=True)
    views = Column(Integer, default=0, nullable=True)
    applications = Column(Integer, default=0, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships - added to support new job applications and saved jobs
    job_applications = relationship("JobApplication", back_populates="job", cascade="all, delete-orphan")
    saved_by_candidates = relationship("SavedJob", back_populates="job", cascade="all, delete-orphan")
    pitches = relationship("CandidatePitch", back_populates="job")

    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.title}', status='{self.status}')>"

class CandidatePitch(Base):
    __tablename__ = "candidate_pitches"
    
    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True)  # ID of the user who saved the pitch
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=True)  # Can be null if not associated with specific candidate
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)  # Can be null if not associated with specific job
    title = Column(String(255), nullable=False)  # Title of the saved pitch
    content = Column(Text, nullable=False)  # The actual pitch content
    notes = Column(Text, nullable=True)  # Optional notes from the user
    tags = Column(String(255), nullable=True)  # Comma-separated tags for organization
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="pitches")
    job = relationship("Job", back_populates="pitches")

@event.listens_for(Candidate.skills, "append", retval=True)
def _convert_skill_to_object(target, value, initiator):
    """Convert str skill names to Skill instances for Candidate.skills."""
    if isinstance(value, str):
        return Skill(name=value.strip())
    return value


# ====================================================================
# Pydantic Models for Data Validation/Serialization (e.g., Resume Parsing)
# ====================================================================


class Section(BaseModel):
    """A section of a resume with its title and content."""
    title: str
    content: str
    markdown_content: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

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
    # Internal field, might not be needed in the final model exposed via API
    # Rename to remove leading underscore
    all_location_candidates: Optional[List[str]] = Field(None, exclude=True)
    
    @validator('name', 'first_name', 'last_name', pre=True)
    def normalize_name_casing(cls, v):
        """Normalize name casing to proper format (First Last)"""
        if not v or not isinstance(v, str):
            return v
        
        # Clean up the name
        name = v.strip()
        if not name:
            return v
        
        # Handle common cases
        # If it's already properly cased, return as is
        if name == name.title():
            return name
        
        # If it's all caps, convert to title case
        if name.isupper():
            return name.title()
        
        # If it's all lowercase, convert to title case
        if name.islower():
            return name.title()
        
        # For mixed cases, try to normalize
        # Split by spaces and handle each part
        name_parts = name.split()
        normalized_parts = []
        
        for part in name_parts:
            part = part.strip()
            if not part:
                continue
            
            # Handle special cases like "Jr.", "Sr.", "III", "IV", etc.
            if part.upper() in ['JR', 'SR', 'JR.', 'SR.', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']:
                normalized_parts.append(part.upper())
            # Handle common prefixes like "Mc", "Mac", "O'", etc.
            elif part.lower().startswith(('mc', 'mac', "o'", "d'", "l'")):
                if len(part) > 2:
                    normalized_parts.append(part[0].upper() + part[1:].lower())
                else:
                    normalized_parts.append(part.title())
            # Handle hyphens (e.g., "Jean-Pierre")
            elif '-' in part:
                hyphen_parts = part.split('-')
                normalized_hyphen_parts = []
                for hp in hyphen_parts:
                    if hp:
                        normalized_hyphen_parts.append(hp[0].upper() + hp[1:].lower())
                normalized_parts.append('-'.join(normalized_hyphen_parts))
            else:
                # Standard case: first letter uppercase, rest lowercase
                normalized_parts.append(part[0].upper() + part[1:].lower())
        
        return ' '.join(normalized_parts)


class Experience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    date_range: Optional[str] = None # Raw extracted date string
    start_date: Optional[date] = None # Parsed start date
    end_date: Optional[date] = None   # Parsed end date (can be None for current)
    description: Optional[str] = None
    achievements: Optional[List[str]] = []
    technologies: Optional[List[str]] = []


class Education(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    location: Optional[str] = None
    date_range: Optional[str] = None # Raw extracted date string
    start_date: Optional[date] = None # Parsed start date
    end_date: Optional[date] = None   # Parsed end date
    gpa: Optional[float] = None
    description: Optional[str] = None


class SkillSchema(BaseModel): # Note: This is the Pydantic Skill model
    name: str
    category: Optional[str] = 'Other' # e.g., 'Programming Language', 'Framework', 'Database'
    level: Optional[str] = None # e.g., 'Beginner', 'Intermediate', 'Advanced'


class Project(BaseModel):
    """Project information."""
    name: str
    description: Optional[str] = None
    technologies: List[str] = []
    url: Optional[str] = None
    date_range: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    achievements: List[str] = []
    role: Optional[str] = None


class Certification(BaseModel):
    """Certification information."""
    name: str
    issuer: Optional[str] = None
    date: Optional[str] = None
    issued_date: Optional[date] = None
    expires: Optional[str] = None
    expiry_date: Optional[date] = None
    credential_id: Optional[str] = None
    url: Optional[str] = None


class Language(BaseModel):
    """Language proficiency information."""
    name: str = Field(alias="language")
    proficiency: Optional[str] = None
    certification: Optional[str] = None


class Publication(BaseModel):
    """Publication information."""
    title: str
    publisher: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None


class Volunteer(BaseModel):
    """Volunteer experience information."""
    organization: str
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


class ResumeData(BaseModel):
    # Metadata
    file_id: str # Unique ID for the parsing instance
    file_name: Optional[str] = None
    content_type: Optional[str] = None

    # Content
    full_text: str
    markdown_text: Optional[str] = None
    sections: List[Section] = [] # Changed from Dict to List of Section objects

    # Extracted Structured Data
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: Optional[str] = None
    experience: List[Experience] = []
    education: List[Education] = []
    skills: List[Union[SkillSchema, str]] = [] # Updated to allow both SkillSchema and strings
    skill_categories: Optional[Dict[str, List[str]]] = None
    # Added other potential sections
    projects: List[Project] = []
    certifications: List[Certification] = []
    languages: List[Language] = []
    publications: List[Publication] = []
    volunteer: List[Volunteer] = []
    raw_entities: Dict = {}
    embeddings: Dict = {}
    metadata: Dict = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Add the missing Skill model for compatibility
class Skill(Base):
    __tablename__ = "skills"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    category = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), index=True, nullable=False)  # To group memories by conversation/task
    agent_name = Column(String(100), nullable=False, index=True)
    memory_type = Column(String(50), nullable=False)  # e.g., 'observation', 'reflection', 'action_result'
    content = Column(JSON, nullable=False)  # Flexible field for memory data
    importance = Column(Float, default=0.5) # A score from 0.0 to 1.0
    embedding = Column(Vector(384)) # Using 384 dimensions from all-MiniLM-L6-v2
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_agent_session_time', 'agent_name', 'session_id', 'created_at'),
    )

    def __repr__(self):
        return f"<AgentMemory(id={self.id}, agent='{self.agent_name}', type='{self.memory_type}')>"

# Job Applications model
class JobApplication(Base):
    """Model for job applications."""
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False)
    status = Column(String(50), default="submitted", nullable=False)  # submitted, reviewing, interviewing, accepted, rejected
    cover_letter = Column(Text, nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional tracking fields
    source = Column(String(100), default="direct", nullable=True)  # where they applied from
    notes = Column(Text, nullable=True)  # recruiter notes
    
    # Relationships
    job = relationship("Job", back_populates="job_applications")
    candidate = relationship("Candidate", back_populates="candidate_applications")

    def __repr__(self):
        return f"<JobApplication(job_id={self.job_id}, candidate_id={self.candidate_id}, status='{self.status}')>"


# Saved Jobs model
class SavedJob(Base):
    """Model for jobs saved by candidates."""
    __tablename__ = "saved_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False)
    saved_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)  # candidate's personal notes about the job
    
    # Relationships
    job = relationship("Job", back_populates="saved_by_candidates")
    candidate = relationship("Candidate", back_populates="saved_jobs")

    # Ensure a candidate can't save the same job twice
    __table_args__ = (UniqueConstraint('job_id', 'candidate_id', name='unique_job_candidate_save'),)

    def __repr__(self):
        return f"<SavedJob(job_id={self.job_id}, candidate_id={self.candidate_id})>"
