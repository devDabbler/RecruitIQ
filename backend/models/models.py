import uuid
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Table, UniqueConstraint, event, Float, Index, Boolean, SmallInteger, CheckConstraint, BigInteger, func
from sqlalchemy.dialects.postgresql import JSONB
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
    embedding = Column(Vector(768), nullable=True)  # nomic-embed-text over position+company+headline+skills
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
    # ATS Phase B: optional links to team members. The free-text columns
    # above stay for display and seed data (spec 3.2).
    hiring_manager_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recruiter_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    application_deadline = Column(DateTime, nullable=True)
    start_date = Column(DateTime, nullable=True)
    job_metadata = Column(JSON, nullable=True)
    status = Column(String(50), default="open")
    skills = Column(String, nullable=True)
    # Track 2 Phase 1: must-have / nice-to-have skills, years range, minimum
    # education. Shape and limits live in services/job_requirements.py.
    requirements = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)  # SQLite in two legacy tests
    views = Column(Integer, default=0, nullable=True)
    applications = Column(Integer, default=0, nullable=True)
    embedding = Column(Vector(768), nullable=True)  # nomic-embed-text over title+overview+quals+skills
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships - added to support new job applications and saved jobs
    job_applications = relationship("JobApplication", back_populates="job", cascade="all, delete-orphan")
    saved_by_candidates = relationship("SavedJob", back_populates="job", cascade="all, delete-orphan")
    pitches = relationship("CandidatePitch", back_populates="job")
    pipeline_stages = relationship(
        "PipelineStage",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="PipelineStage.position",
    )

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
    embedding = Column(Vector(768)) # 768 dimensions from nomic-embed-text
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_agent_session_time', 'agent_name', 'session_id', 'created_at'),
    )

    def __repr__(self):
        return f"<AgentMemory(id={self.id}, agent='{self.agent_name}', type='{self.memory_type}')>"


class User(Base):
    """An operator of the platform.

    Five roles (ATS Phase B): admin, hiring_manager, hiring_team, and
    interviewer are staff; demo is the read-only public account, created on
    demand by POST /auth/demo so a visitor following a link never meets a
    login screen. What each role may do lives in backend/utils/permissions.py.
    Registration, password reset, and refresh-token rotation are out of
    scope for a portfolio demo (Phase 3 spec Â§2).
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # null for the demo user
    role = Column(String(20), nullable=False, default="demo")
    # ATS Phase B. Roles: admin, hiring_manager, hiring_team, interviewer, demo.
    name = Column(String(100), nullable=True)
    timezone = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role}')>"


# Job Applications model
class JobApplication(Base):
    """Model for job applications."""
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False)
    status = Column(String(50), default="active", nullable=False)  # active, hired, rejected, declined, withdrawn (ATS Phase A)
    cover_letter = Column(Text, nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional tracking fields
    source = Column(String(100), default="direct", nullable=True)  # where they applied from
    notes = Column(Text, nullable=True)  # recruiter notes

    # ATS Phase E: the candidate status link. Null means no link is active;
    # regenerating replaces it, which is how a leaked link is revoked.
    public_token = Column(String(36), nullable=True, unique=True, index=True)
    public_token_created_at = Column(DateTime, nullable=True)

    # Relationships
    job = relationship("Job", back_populates="job_applications")
    candidate = relationship("Candidate", back_populates="candidate_applications")
    stages = relationship(
        "ApplicationStage",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationStage.id",
    )

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


# ====================================================================
# Pipeline (ATS Phase A, spec 2026-10-03 section 3)
# ====================================================================


class PipelineStage(Base):
    """One stage of one job's pipeline.

    Copied from `pipeline_service.DEFAULT_STAGES` when a job is created or the
    first time its pipeline is read. `kind` is `round` (something the candidate
    goes through) or `outcome` (where they end up). Disabled rounds are skipped
    by every transition.
    """
    __tablename__ = "pipeline_stages"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    kind = Column(String(20), nullable=False, default="round")
    position = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("job_id", "key", name="uq_pipeline_stage_job_key"),)

    job = relationship("Job", back_populates="pipeline_stages")
    default_interviewers = relationship(
        "StageDefaultInterviewer", cascade="all, delete-orphan", back_populates="stage"
    )

    def __repr__(self):
        return f"<PipelineStage(job_id={self.job_id}, key='{self.key}', enabled={self.enabled})>"


class ApplicationStage(Base):
    """Where one application stands at one stage. Together these rows are the history."""
    __tablename__ = "application_stages"

    id = Column(Integer, primary_key=True)
    application_id = Column(
        Integer, ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id = Column(
        Integer, ForeignKey("pipeline_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    changed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("application_id", "stage_id", name="uq_application_stage"),
    )

    application = relationship("JobApplication", back_populates="stages")
    stage = relationship("PipelineStage")
    interviews = relationship(
        "Interview",
        back_populates="application_stage",
        cascade="all, delete-orphan",
        order_by="Interview.id",
    )

    def __repr__(self):
        return f"<ApplicationStage(application_id={self.application_id}, stage_id={self.stage_id}, status='{self.status}')>"


# ====================================================================
# Interviews and feedback (ATS Phase B, spec 2026-10-03 section 3.1)
# ====================================================================


class Interview(Base):
    """One interviewer assigned to one stage of one application."""
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True)
    application_stage_id = Column(
        Integer, ForeignKey("application_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assignment_source = Column(String(20), nullable=False, default="manual")  # manual or default
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("application_stage_id", "interviewer_id", name="uq_interview_stage_interviewer"),
    )

    application_stage = relationship("ApplicationStage", back_populates="interviews")
    interviewer = relationship("User")
    feedback = relationship(
        "Feedback", back_populates="interview", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def submitted_feedback(self):
        """The feedback, if submitted. A draft does not count as given."""
        feedback = self.feedback
        return feedback if feedback is not None and feedback.status == "submitted" else None

    @property
    def draft_feedback(self):
        feedback = self.feedback
        return feedback if feedback is not None and feedback.status == "draft" else None

    def __repr__(self):
        return f"<Interview(stage_row={self.application_stage_id}, interviewer={self.interviewer_id})>"


class Feedback(Base):
    """What one interviewer thought. Never read by the scorer (transparency page)."""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    interview_id = Column(
        Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Track 2 Phase 4: a draft may be partial and is seen only by its author.
    # Everything that reads "has this interviewer given feedback" must ask for
    # status == submitted (Interview.submitted_feedback), never just a row.
    status = Column(String(10), nullable=False, default="submitted", server_default="submitted")
    rating = Column(SmallInteger, nullable=True)
    recommendation = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    # NULL while a draft (written explicitly); the server default covers raw inserts.
    submitted_at = Column(DateTime, nullable=True, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
        CheckConstraint("status IN ('draft', 'submitted')", name="ck_feedback_status"),
        CheckConstraint(
            "status = 'draft' OR (rating IS NOT NULL AND recommendation IS NOT NULL AND submitted_at IS NOT NULL)",
            name="ck_feedback_submitted_complete",
        ),
    )

    interview = relationship("Interview", back_populates="feedback")

    @property
    def is_draft(self) -> bool:
        return self.status == "draft"


class FeedbackTemplate(Base):
    """Starting text for an interviewer's notes. Global when job_id is NULL.
    Not candidate data (Track 2 Phase 4)."""
    __tablename__ = "feedback_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    body = Column(Text, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())


class StageDefaultInterviewer(Base):
    """Assigned automatically when an application enters this stage."""
    __tablename__ = "stage_default_interviewers"

    id = Column(Integer, primary_key=True)
    pipeline_stage_id = Column(
        Integer, ForeignKey("pipeline_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("pipeline_stage_id", "user_id", name="uq_stage_default_interviewer"),
    )

    stage = relationship("PipelineStage", back_populates="default_interviewers")
    user = relationship("User")


# ====================================================================
# Notes and tags (ATS Phase C, spec 2026-10-03 section 3.1)
# ====================================================================


class Note(Base):
    """One entry in a candidate's notes thread.

    `application_id` and `stage_id` are both null for a note about the person,
    and both set for a note about one stage of one application. `author_id` is
    null only for text imported from the old `candidates.notes` column. The
    three SET NULL foreign keys mean deleting a job or a user never deletes what
    someone wrote about a candidate; the note just loses its label.
    """
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(
        String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id = Column(
        Integer, ForeignKey("job_applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stage_id = Column(Integer, ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    author = relationship("User")
    application = relationship("JobApplication")
    stage = relationship("PipelineStage")

    def __repr__(self):
        return f"<Note(candidate_id={self.candidate_id}, application_id={self.application_id})>"


class CandidateTag(Base):
    """A lower-kebab-case label on a candidate. Normalized on write by `utils.tags`."""
    __tablename__ = "candidate_tags"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(
        String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("candidate_id", "tag", name="uq_candidate_tag"),)

    def __repr__(self):
        return f"<CandidateTag(candidate_id={self.candidate_id}, tag='{self.tag}')>"


# ====================================================================
# Email (ATS Phase E, spec 2026-10-03 section 3.1)
# ====================================================================


class EmailTemplate(Base):
    """One editable starting point for candidate email. Seeded by migration f7b1d4e5a6c7."""
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EmailLog(Base):
    """Every email sent, or copied to be sent by hand, from the app."""
    __tablename__ = "email_log"

    id = Column(Integer, primary_key=True)
    application_id = Column(
        Integer, ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_key = Column(String(50), nullable=True)
    to_address = Column(String(255), nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False)  # sent, failed, copied
    error = Column(Text, nullable=True)
    sent_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditEvent(Base):
    """One staff request against candidate data (pilot plan Track 1 #3).

    Written by backend/services/audit_service.py, never by handlers directly.
    Identifiers and field names only, never values. Append-only: a trigger
    from migration a9c3e5f7b8d2 refuses UPDATE and DELETE. No foreign keys,
    so an event outlives the candidate and the account it names.
    """
    __tablename__ = "audit_events"

    id = Column(BigInteger, primary_key=True)
    occurred_at = Column(DateTime, nullable=False, server_default=func.now())
    actor_id = Column(String(36), nullable=True)
    actor_role = Column(String(20), nullable=True)
    action = Column(String(16), nullable=False)  # view, create, update, delete, export, process
    subject_type = Column(String(32), nullable=False)
    subject_id = Column(String(64), nullable=True)
    candidate_id = Column(String(36), nullable=True)
    endpoint = Column(String(200), nullable=False)  # "METHOD /route/{template}", never the raw URL
    detail = Column(String(64), nullable=True)
    fields = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)  # SQLite in two legacy tests
    status_code = Column(SmallInteger, nullable=False)
