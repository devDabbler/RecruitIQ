"""
Enhanced matching router for the Recruiter Dashboard.
This module provides improved endpoints for job-candidate matching.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from backend.utils.database import get_db
from backend.models.models import Job, Candidate
from backend.services.agent_framework.agent_factory import AgentFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enhanced-matching", tags=["enhanced-matching"])

# Request Models
class CandidateMatchRequest(BaseModel):
    job_ids: List[int]
    min_score: Optional[float] = 20.0

class JobMatchRequest(BaseModel):
    candidate_id: str
    min_score: Optional[float] = 20.0

class SimilarJobsRequest(BaseModel):
    job_id: int
    limit: Optional[int] = 5

# Response Models
class JobMatchResult(BaseModel):
    id: int
    title: str
    department: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    skills: List[str] = []
    match_score: float
    match_explanation: str
    skill_match_score: Optional[float] = None
    role_match_score: Optional[float] = None
    experience_match_score: Optional[float] = None

class CandidateMatchResult(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    resume_id: Optional[int] = None
    skills: List[str] = []
    position: Optional[str] = None
    experience_level: Optional[str] = None
    years_experience: Optional[int] = None
    match_score: float
    match_explanation: str
    skill_match_score: Optional[float] = None
    role_match_score: Optional[float] = None
    experience_match_score: Optional[float] = None

class MatchJobsResponse(BaseModel):
    jobs: List[JobMatchResult]

class MatchCandidatesResponse(BaseModel):
    candidates: List[CandidateMatchResult]

class SimilarJobResult(BaseModel):
    id: int
    title: str
    department: Optional[str] = None
    location: Optional[str] = None
    skills: List[str] = []
    similarity_score: float
    similarity_explanation: str

class SimilarJobsResponse(BaseModel):
    similar_jobs: List[SimilarJobResult]



@router.post("/match-jobs", response_model=MatchJobsResponse)
async def match_jobs_for_candidate(
    request: JobMatchRequest,
    db: Session = Depends(get_db)
):
    """Find jobs that match the given candidate using enhanced matching."""
    try:
        # Log the incoming request
        logger.info(f"Received enhanced match_jobs request: {request.dict()}")
        
        agent = AgentFactory.create_agent("matching")
        task = {
            "type": "jobs_for_candidate",
            "candidate_id": request.candidate_id,
            "db": db,
            "min_score": request.min_score,
            "limit": 10
        }
        results = await agent.execute(task)

        # The agent returns a dictionary, so extract the actual list of jobs from the 'results' key.
        job_list = results.get("results", []) if isinstance(results, dict) else []
        if not isinstance(job_list, list):
            # Fallback if 'results' is not a list
            logger.warning(f"Agent returned unexpected format for results. Expected list, got {type(job_list)}. Full agent response: {results}")
            job_list = []
            
        return MatchJobsResponse(jobs=job_list)
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error in enhanced match_jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing match: {str(e)}")

@router.post("/match-candidates", response_model=MatchCandidatesResponse)
async def match_candidates_for_jobs(
    request: CandidateMatchRequest,
    db: Session = Depends(get_db)
):
    """Find candidates that match the given jobs using enhanced matching."""
    try:
        # Log the incoming request
        logger.info(f"Received enhanced match_candidates request: {request.dict()}")
        
        # Validate at least one job ID
        if not request.job_ids:
            raise HTTPException(status_code=422, detail="At least one job_id is required")
        
        # Validate jobs exist
        for job_id in request.job_ids:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
        
        # Currently we only support matching one job at a time with the enhanced matching
        # Use the first job ID from the list (can be extended to support multiple jobs)
        job_id = request.job_ids[0] if request.job_ids else None
        if not job_id:
            raise HTTPException(status_code=400, detail="At least one job_id is required.")

        agent = AgentFactory.create_agent("matching")
        task = {
            "type": "candidates_for_job",
            "job_id": job_id,
            "strategy": "enhanced",
            "db": db,
            "min_score": request.min_score,
            "limit": 10
        }
        results = await agent.execute(task)

        # The agent returns a dictionary, so extract the actual list of candidates from the 'results' key.
        candidate_list = results.get("results", []) if isinstance(results, dict) else []
        if not isinstance(candidate_list, list):
             # Fallback if 'results' is not a list
            logger.warning(f"Agent returned unexpected format for results. Expected list, got {type(candidate_list)}. Full agent response: {results}")
            candidate_list = []

        return MatchCandidatesResponse(candidates=candidate_list)
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error in enhanced match_candidates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing match: {str(e)}")

@router.post("/similar-jobs", response_model=SimilarJobsResponse)
async def find_similar_jobs(
    request: SimilarJobsRequest,
    db: Session = Depends(get_db)
):
    """Find jobs similar to the given job."""
    try:
        # Log the incoming request
        logger.info(f"Received similar_jobs request: {request.dict()}")
        
        agent = AgentFactory.create_agent("matching")
        task = {
            "type": "similar_jobs",
            "job_id": request.job_id,
            "db": db,
            "limit": request.limit
        }
        results = await agent.execute(task)
        return SimilarJobsResponse(similar_jobs=results)
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error finding similar jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
