"""
Enhanced matching router for the Recruiter Dashboard.
This module provides improved endpoints for job-candidate matching.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import asyncio
import logging

from backend.utils.database import get_db
from backend.models.models import Job, Candidate
from backend.services.agent_framework.agent_factory import AgentFactory
from backend.services.access_service import SCORE_HIDDEN_DETAIL, can_see_score, request_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enhanced-matching", tags=["enhanced-matching"])

# Request Models
# min_score is a plain float, not Optional: an explicit JSON null used to pass
# validation, reach `match_score >= None` in the integrator, and come back as
# an empty 200 that looked like "nobody matches".
class CandidateMatchRequest(BaseModel):
    job_ids: List[int]
    min_score: float = 20.0

class JobMatchRequest(BaseModel):
    candidate_id: str
    min_score: float = 20.0

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


def _run_matching_agent(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run a matching task and return its result list, or raise.

    The endpoints below are plain `def` so FastAPI runs them in the
    threadpool. Scoring is synchronous ORM plus one embedding call per title
    (about 8s for /matching); as `async def` that all ran on the event loop
    and stalled every other request on the worker until it finished. The
    agent's methods are coroutines that never actually await, so a private
    event loop in the worker thread drives them.

    The agent reports failure as {"status": "error"} rather than raising.
    Unwrapping that to an empty list returned a 200 that read as "no
    matches", so it is surfaced as a 500 instead.
    """
    results = asyncio.run(AgentFactory.create_agent("matching").execute(task))
    if not isinstance(results, dict):
        logger.warning(f"Matching agent returned {type(results)}, expected dict: {results}")
        return []
    if results.get("status") == "error":
        raise HTTPException(status_code=500, detail=f"Error processing match: {results.get('message')}")
    items = results.get("results", [])
    if not isinstance(items, list):
        logger.warning(f"Agent returned unexpected format for results. Expected list, got {type(items)}. Full agent response: {results}")
        return []
    return items


@router.post("/match-jobs", response_model=MatchJobsResponse)
def match_jobs_for_candidate(
    request: JobMatchRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Find jobs that match the given candidate using enhanced matching."""
    # ATS Phase B: interviewers see scores only after giving feedback.
    if not can_see_score(db, request_user(http_request), request.candidate_id):
        raise HTTPException(status_code=403, detail=SCORE_HIDDEN_DETAIL)
    try:
        # Log the incoming request
        logger.info(f"Received enhanced match_jobs request: {request.dict()}")

        task = {
            "type": "jobs_for_candidate",
            "candidate_id": request.candidate_id,
            "db": db,
            "min_score": request.min_score,
            "limit": 10
        }
        return MatchJobsResponse(jobs=_run_matching_agent(task))
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error in enhanced match_jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing match: {str(e)}")

@router.post("/match-candidates", response_model=MatchCandidatesResponse)
def match_candidates_for_jobs(
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

        task = {
            "type": "candidates_for_job",
            "job_id": job_id,
            "strategy": "enhanced",
            "db": db,
            "min_score": request.min_score,
            "limit": 10
        }
        return MatchCandidatesResponse(candidates=_run_matching_agent(task))
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error in enhanced match_candidates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing match: {str(e)}")

@router.post("/similar-jobs", response_model=SimilarJobsResponse)
def find_similar_jobs(
    request: SimilarJobsRequest,
    db: Session = Depends(get_db)
):
    """Find jobs similar to the given job."""
    try:
        # Log the incoming request
        logger.info(f"Received similar_jobs request: {request.dict()}")

        task = {
            "type": "similar_jobs",
            "job_id": request.job_id,
            "db": db,
            "limit": request.limit
        }
        # This passed the agent's whole envelope dict as the list, so every
        # call failed response validation and returned a 500.
        return SimilarJobsResponse(similar_jobs=_run_matching_agent(task))
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error finding similar jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
