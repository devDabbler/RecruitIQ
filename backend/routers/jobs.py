from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import json

from ..utils.database import get_db
from ..models.job import (
    JobCreateUpdate,
    JobResponse,
    JobSearchResponse,
    JobStatus,
    JobType,
    LocationType,
    ExperienceLevel
)
from ..models.models import Job, Candidate, Resume, JobApplication, SavedJob
from ..services.service_registry import (
    provide_job_service,
    provide_llm_service,
    provide_graph_service,
)

# Additional models for candidate matching
class CandidateMatch(BaseModel):
    """Model for a candidate match."""
    # Candidate ids are UUID strings, and a candidate may have no resume row.
    # Mirrors CandidateMatchResult in enhanced_matching.py, which was updated
    # for the UUID migration while this model was not.
    id: str
    name: str
    email: Optional[str] = None
    resume_id: Optional[int] = None
    match_score: float

class CandidateMatchesResponse(BaseModel):
    """Model for candidate matches response."""
    job_id: int
    job_title: str
    candidates: List[CandidateMatch]

# New models for job actions
class JobApplicationCreate(BaseModel):
    """Model for creating a job application."""
    candidate_id: str
    cover_letter: Optional[str] = None
    source: Optional[str] = "direct"

class JobApplicationResponse(BaseModel):
    """Model for job application response."""
    id: int
    job_id: int
    candidate_id: str
    status: str
    applied_at: str
    source: Optional[str] = None

class SavedJobCreate(BaseModel):
    """Model for saving a job."""
    candidate_id: str
    notes: Optional[str] = None

class SavedJobResponse(BaseModel):
    """Model for saved job response."""
    id: int
    job_id: int
    candidate_id: str
    saved_at: str
    notes: Optional[str] = None

router = APIRouter(prefix="/jobs")

import logging
from fastapi import HTTPException

@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    job: JobCreateUpdate,
    db: Session = Depends(get_db),
    job_service = Depends(provide_job_service),
    llm_service = Depends(provide_llm_service),
    graph_service = Depends(provide_graph_service)
):
    """
    Create a new job posting.
    NOTE: Always POST to /jobs/ (with trailing slash) to avoid redirect issues.
    """
    logger = logging.getLogger("backend.routers.jobs")
    try:
        # Log incoming job data
        logger.info(f"Received job creation request: {job.dict()}")

        # Convert enum values to strings
        job_data = job.dict()
        job_data["status"] = job.status.value
        job_data["job_type"] = job.job_type.value
        job_data["location_type"] = job.location_type.value
        job_data["experience_level"] = job.experience_level.value

        # Convert skills list to comma-separated string for DB
        skills = job_data.pop("skills", None)
        if skills is not None:
            job_data["skills"] = ",".join(skills) if skills else None

        # Remove any legacy fields that may be present
        job_data.pop("description", None)
        job_data.pop("requirements", None)
        job_data.pop("responsibilities", None)

        # Create job in database
        db_job = Job(**job_data)
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        
        # Generate and store embeddings
        try:
            job_service.store_job_embeddings(db, db_job.id)
            logger.info(f"Generated and stored embeddings for job {db_job.id}")
        except Exception as e:
            logger.error(f"Error generating embeddings for job {db_job.id}: {str(e)}")
            # Continue even if embedding generation fails

        # Convert skills back to list for response
        if isinstance(db_job.skills, str) and db_job.skills:
            db_job.skills = db_job.skills.split(",")
        else:
            db_job.skills = []

        logger.info(f"Successfully created job with ID {db_job.id}")
        return db_job
    except Exception as e:
        logger.error(f"Error creating job: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to create job: {str(e)}")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    job_service = Depends(provide_job_service),
    llm_service = Depends(provide_llm_service),
    graph_service = Depends(provide_graph_service)
):
    """Get job by ID."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID {job_id} not found"
        )
    
    # Convert skills string to list
    if isinstance(job.skills, str) and job.skills:
        job.skills = job.skills.split(",")
    else:
        job.skills = []
    
    return job

@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: int,
    job_update: JobCreateUpdate,
    db: Session = Depends(get_db),
    job_service = Depends(provide_job_service),
    llm_service = Depends(provide_llm_service),
    graph_service = Depends(provide_graph_service)
):
    """Update an existing job posting."""
    db_job = db.query(Job).filter(Job.id == job_id).first()
    
    if not db_job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID {job_id} not found"
        )
    
    # Update the fields that are provided
    update_data = job_update.dict(exclude_unset=True)
    
    # Handle enum conversions
    if "status" in update_data and update_data["status"]:
        update_data["status"] = update_data["status"].value
    
    if "job_type" in update_data and update_data["job_type"]:
        update_data["job_type"] = update_data["job_type"].value
    
    if "location_type" in update_data and update_data["location_type"]:
        update_data["location_type"] = update_data["location_type"].value
    
    if "experience_level" in update_data and update_data["experience_level"]:
        update_data["experience_level"] = update_data["experience_level"].value
    
    # Handle skills list
    if "skills" in update_data and update_data["skills"]:
        update_data["skills"] = ",".join(update_data["skills"])
    
    for key, value in update_data.items():
        setattr(db_job, key, value)
    
    db.commit()
    db.refresh(db_job)
    
    # Update embeddings
    try:
        job_service.store_job_embeddings(db, db_job.id)
        logger.info(f"Updated embeddings for job {db_job.id}")
    except Exception as e:
        logger.error(f"Error updating embeddings for job {db_job.id}: {str(e)}")
        # Continue even if embedding update fails
    
    # Convert skills string back to list for response
    if isinstance(db_job.skills, str) and db_job.skills:
        db_job.skills = db_job.skills.split(",")
    else:
        db_job.skills = []
    
    return db_job

from sqlalchemy.exc import SQLAlchemyError

@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    job_service = Depends(provide_job_service),
    llm_service = Depends(provide_llm_service),
    graph_service = Depends(provide_graph_service)
):
    """Delete a job posting and all related records (future-proof)."""
    try:
        db_job = db.query(Job).filter(Job.id == job_id).first()
        if not db_job:
            raise HTTPException(
                status_code=404,
                detail=f"Job with ID {job_id} not found"
            )

        # TODO: Delete related records if needed (e.g., applications, analytics)
        db.delete(db_job)
        db.commit()
        return {"message": f"Job with ID {job_id} and all related data deleted successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during deletion: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

from backend.services.agent_framework.agent_factory import AgentFactory
from backend.services.service_registry import provide_matching_integrator

@router.get("/{job_id}/matching-candidates", response_model=CandidateMatchesResponse)
async def get_matching_candidates(
    job_id: int,
    limit: int = Query(10, description="Maximum number of candidates to return"),
    db: Session = Depends(get_db),
    matching_integrator = Depends(provide_matching_integrator)
):
    """Get candidates that match a job posting using Agentic Zero (CandidateMatchingAgent)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")

    try:
        agent = AgentFactory.create_agent("matching", matching_integrator=matching_integrator)
        # The task dict follows the agent's contract
        task = {
            "job_id": job_id,
            "strategy": "enhanced",
            "db": db,
            "min_score": 40.0,
            "limit": limit
        }
        agentic_result = await agent.execute(task)
        if agentic_result.get("status") != "completed":
            raise HTTPException(status_code=500, detail=f"Agentic matching failed: {agentic_result.get('message')}")
        # agentic_result["results"] is expected to be a list of matches
        matches = agentic_result.get("results")
        if isinstance(matches, dict) and "matches" in matches:
            matches = matches["matches"]
        if not isinstance(matches, list):
            matches = []
        # Convert to CandidateMatch models for response
        candidates = [CandidateMatch(
            id=m.get("id"),
            name=m.get("name", ""),
            email=m.get("email", ""),
            resume_id=m.get("resume_id"),
            match_score=m.get("match_score", 0.0)
        ) for m in matches]
        return CandidateMatchesResponse(
            job_id=job.id,
            job_title=job.title,
            candidates=candidates
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding matching candidates (agentic): {str(e)}")

@router.get("/", response_model=JobSearchResponse)
async def search_jobs(
    keyword: Optional[str] = None,
    department: Optional[str] = None,
    location: Optional[str] = None,
    location_type: Optional[LocationType] = None,
    job_type: Optional[JobType] = None,
    experience_level: Optional[ExperienceLevel] = None,
    status: Optional[JobStatus] = None,
    min_salary: Optional[int] = None,
    max_salary: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    job_service = Depends(provide_job_service),
    llm_service = Depends(provide_llm_service),
    graph_service = Depends(provide_graph_service)
):
    """Search for jobs with various filters."""
    query = db.query(Job)
    
    # Apply filters
    if keyword:
        query = query.filter(
            (Job.title.ilike(f"%{keyword}%")) |
            (Job.job_overview.ilike(f"%{keyword}%")) |
            (Job.required_qualifications.ilike(f"%{keyword}%"))
        )
    
    if department:
        query = query.filter(Job.department.ilike(f"%{department}%"))
    
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    
    if location_type:
        query = query.filter(Job.location_type == location_type.value)
    
    if job_type:
        query = query.filter(Job.job_type == job_type.value)
    
    if experience_level:
        query = query.filter(Job.experience_level == experience_level.value)
    
    if status:
        query = query.filter(Job.status == status.value)
    
    if min_salary:
        query = query.filter(Job.min_salary >= min_salary)
    
    if max_salary:
        query = query.filter(Job.max_salary <= max_salary)
    
    # Count total results for pagination
    total = query.count()
    
    # Apply sorting
    if sort_order.lower() == "asc":
        query = query.order_by(asc(getattr(Job, sort_by)))
    else:
        query = query.order_by(desc(getattr(Job, sort_by)))
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Execute query
    jobs = query.all()
    
    # Process skills for each job
    for job in jobs:
        if isinstance(job.skills, str) and job.skills:
            job.skills = job.skills.split(",")
        else:
            job.skills = []

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": jobs
    }

@router.get("/{job_id}/candidates", response_model=List[dict])
async def get_job_candidates(
    job_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    job_service = Depends(provide_job_service),
    llm_service = Depends(provide_llm_service),
    graph_service = Depends(provide_graph_service)
):
    """Get candidates that have applied for a job."""
    # Verify job exists
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID {job_id} not found"
        )
    
    # Query candidates associated with this job
    query = db.query(Candidate).filter(Candidate.job_id == job_id)
    
    if status:
        query = query.filter(Candidate.status == status)
    
    candidates = query.all()
    
    return [
        {
            "id": candidate.id,
            "first_name": candidate.first_name,
            "last_name": candidate.last_name,
            "email": candidate.email,
            "status": candidate.status,
            "created_at": candidate.created_at
        }
        for candidate in candidates
    ]

@router.post("/{job_id}/track-view")
async def track_job_view(
    job_id: int,
    db: Session = Depends(get_db),
    job_service = Depends(provide_job_service),
    llm_service = Depends(provide_llm_service),
    graph_service = Depends(provide_graph_service)
):
    """Track when a job is viewed (for analytics)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Update view count
    if job.views is None:
        job.views = 0
    job.views += 1
    
    db.commit()
    db.refresh(job)
    
    return {"message": "View tracked", "total_views": job.views}

@router.post("/{job_id}/apply", response_model=JobApplicationResponse)
async def apply_to_job(
    job_id: int,
    application: JobApplicationCreate,
    db: Session = Depends(get_db)
):
    """Apply to a job."""
    logger = logging.getLogger("backend.routers.jobs")
    
    # Check if job exists
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if candidate exists
    candidate = db.query(Candidate).filter(Candidate.id == application.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Check if already applied
    existing_application = db.query(JobApplication).filter(
        JobApplication.job_id == job_id,
        JobApplication.candidate_id == application.candidate_id
    ).first()
    
    if existing_application:
        raise HTTPException(status_code=400, detail="Already applied to this job")
    
    # Create new application
    db_application = JobApplication(
        job_id=job_id,
        candidate_id=application.candidate_id,
        cover_letter=application.cover_letter,
        source=application.source or "direct"
    )
    
    db.add(db_application)
    
    # Update job applications count
    if job.applications is None:
        job.applications = 0
    job.applications += 1
    
    db.commit()
    db.refresh(db_application)
    
    logger.info(f"Application created: job_id={job_id}, candidate_id={application.candidate_id}")
    
    return JobApplicationResponse(
        id=db_application.id,
        job_id=db_application.job_id,
        candidate_id=db_application.candidate_id,
        status=db_application.status,
        applied_at=db_application.applied_at.isoformat(),
        source=db_application.source
    )

@router.post("/{job_id}/save", response_model=SavedJobResponse)
async def save_job(
    job_id: int,
    saved_job: SavedJobCreate,
    db: Session = Depends(get_db)
):
    """Save a job for later."""
    logger = logging.getLogger("backend.routers.jobs")
    
    # Check if job exists
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if candidate exists
    candidate = db.query(Candidate).filter(Candidate.id == saved_job.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Check if already saved
    existing_saved = db.query(SavedJob).filter(
        SavedJob.job_id == job_id,
        SavedJob.candidate_id == saved_job.candidate_id
    ).first()
    
    if existing_saved:
        # Update notes if provided
        if saved_job.notes:
            existing_saved.notes = saved_job.notes
            db.commit()
            db.refresh(existing_saved)
        
        return SavedJobResponse(
            id=existing_saved.id,
            job_id=existing_saved.job_id,
            candidate_id=existing_saved.candidate_id,
            saved_at=existing_saved.saved_at.isoformat(),
            notes=existing_saved.notes
        )
    
    # Create new saved job
    db_saved_job = SavedJob(
        job_id=job_id,
        candidate_id=saved_job.candidate_id,
        notes=saved_job.notes
    )
    
    db.add(db_saved_job)
    db.commit()
    db.refresh(db_saved_job)
    
    logger.info(f"Job saved: job_id={job_id}, candidate_id={saved_job.candidate_id}")
    
    return SavedJobResponse(
        id=db_saved_job.id,
        job_id=db_saved_job.job_id,
        candidate_id=db_saved_job.candidate_id,
        saved_at=db_saved_job.saved_at.isoformat(),
        notes=db_saved_job.notes
    )

@router.get("/applications/{candidate_id}")
async def get_candidate_applications(
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """Get all applications for a candidate."""
    applications = db.query(JobApplication).filter(
        JobApplication.candidate_id == candidate_id
    ).join(Job).all()
    
    return [
        {
            "id": app.id,
            "job_id": app.job_id,
            "job_title": app.job.title,
            "job_department": app.job.department,
            "status": app.status,
            "applied_at": app.applied_at.isoformat(),
            "source": app.source
        }
        for app in applications
    ]

@router.get("/saved/{candidate_id}")
async def get_candidate_saved_jobs(
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """Get all saved jobs for a candidate."""
    saved_jobs = db.query(SavedJob).filter(
        SavedJob.candidate_id == candidate_id
    ).join(Job).all()
    
    return [
        {
            "id": saved.id,
            "job_id": saved.job_id,
            "job_title": saved.job.title,
            "job_department": saved.job.department,
            "job_location": saved.job.location,
            "saved_at": saved.saved_at.isoformat(),
            "notes": saved.notes
        }
        for saved in saved_jobs
    ]
