# backend/routers/matching.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Union  # Removed Dict, Any
from pydantic import BaseModel, ConfigDict, field_validator  # Removed Field
import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc  # Removed func

from backend.utils.database import get_db  # Corrected import path
# Removed unused Settings import

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["matching"])

# Models for request bodies
class CandidateMatchRequest(BaseModel):
    model_config = ConfigDict(strict=True)  # Use strict mode
    job_ids: List[int]
    min_score: Optional[float] = 30.0
    
    @field_validator('job_ids')
    @classmethod
    def validate_job_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one job_id is required")
        
        # Strict validation for integer types
        for job_id in v:
            if not isinstance(job_id, int):
                raise ValueError("All job_ids must be integers")
        return v
        
    @field_validator('min_score')
    @classmethod
    def validate_min_score(cls, v):
        if v < 0 or v > 100:
            raise ValueError("min_score must be between 0 and 100")
        return v

class JobMatchRequest(BaseModel):
    candidate_id: str  # Changed from int to str
    min_score: Optional[float] = 30.0

class MatchReportRequest(BaseModel):
    job_id: int
    candidate_id: Union[int, str]  # Handle both integer IDs and UUID strings

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

class MatchJobsResponse(BaseModel):
    jobs: List[JobMatchResult]

@router.post("/match_candidates", status_code=status.HTTP_200_OK)
async def match_candidates_for_jobs(
    request: CandidateMatchRequest,
    db: Session = Depends(get_db),
):
    """Find candidates that match the given jobs (Agentic Zero)"""
    from backend.services.agent_framework.agent_factory import AgentFactory
    try:
        # AGENTIC ZERO MIGRATION: Use CandidateMatchingAgent via AgentFactory
        agent = AgentFactory.create_agent("matching")
        # Only the first job_id is used for now (expand for multi-job matching as needed)
        job_id = request.job_ids[0] if request.job_ids else None
        if not job_id:
            raise HTTPException(status_code=400, detail="At least one job_id is required.")
        task = {
            "job_id": job_id,
            "strategy": "enhanced",
            "db": db,
            "min_score": request.min_score,
            "limit": 10
        }
        results = await agent.execute(task)
        # Always return a list for frontend compatibility
        return [results] if isinstance(results, dict) else results
    except Exception as e:
        logger.exception(f"Agentic Zero error in match_candidates_for_jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match_jobs")
async def match_jobs_for_candidate(
    request: JobMatchRequest,
    db: Session = Depends(get_db),
):
    """Find jobs that match the given candidate (Agentic Zero)"""
    from backend.services.agent_framework.agent_factory import AgentFactory
    try:
        # AGENTIC ZERO MIGRATION: Use CandidateMatchingAgent for job matching
        agent = AgentFactory.create_agent("matching")
        task = {
            "type": "jobs_for_candidate",
            "candidate_id": request.candidate_id,
            "db": db,
            "min_score": request.min_score if request.min_score > 0 else 20.0,  # Lower default for tighter matching
            "limit": 10
        }
        results = await agent.execute(task)
        return results
    except Exception as e:
        logger.exception(f"Agentic Zero error in match_jobs_for_candidate: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    # LEGACY LOGIC (commented out for migration):
    # try:
    #     ... (legacy code omitted for brevity)
    # except Exception as e:
    #     logger.exception(f"Error matching jobs for candidate: {str(e)}")
    #     raise HTTPException(status_code=500, detail="Internal server error during job matching")


@router.post("/match_report")
async def generate_match_report(
    request: MatchReportRequest,
    db: Session = Depends(get_db),
):
    """Generate a detailed match report between a job and candidate (Agentic Zero)"""
    from backend.services.agent_framework.agent_factory import AgentFactory
    try:
        # AGENTIC ZERO MIGRATION: Use JobAnalysisAgent via AgentFactory (or a dedicated report agent if defined)
        agent = AgentFactory.create_agent("job")
        task = {
            "job_id": request.job_id,
            "candidate_id": request.candidate_id,
            "db": db,
            "action": "generate_match_report"
        }
        results = await agent.execute(task)
        return results
    except Exception as e:
        logger.exception(f"Agentic Zero error in generate_match_report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    # LEGACY LOGIC (commented out for migration):
    # try:
    #     # Get the required services
    #     from backend.services.llm_service import get_llm_service
    #     llm_service = get_llm_service()
        
    #     # Get the job and candidate details
    #     from backend.models.models import Job, Candidate, Resume
        
    #     job = db.query(Job).filter(Job.id == request.job_id).first()
    #     if not job:
    #         raise HTTPException(status_code=404, detail=f"Job with ID {request.job_id} not found")
        
    #     # Handle both integer IDs and UUID strings for candidates
    #     try:
    #         candidate_id = request.candidate_id
    #         # Try different lookup approaches based on ID type
    #         candidate = None
            
    #         # Try direct lookup first
    #         candidate = db.query(Candidate).filter(Candidate.id == str(candidate_id)).first()
            
    #         # If that fails and ID is a string, try case-insensitive comparison
    #         if not candidate and isinstance(candidate_id, str):
    #             # Use string casting and lowercase comparison for flexibility
    #             candidates = db.query(Candidate).all()
    #             for c in candidates:
    #                 if str(c.id).lower() == str(candidate_id).lower():
    #                     candidate = c
    #                     break
            
    #         if not candidate:
    #             raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found")
                
    #     except Exception as e:
    #         logger.error(f"Error looking up candidate: {str(e)}")
    #         raise HTTPException(status_code=500, detail=f"Error processing candidate lookup: {str(e)}")
            
    #     # Get the most recent resume
    #     resume = db.query(Resume).filter(
    #         Resume.candidate_id == candidate.id
    #     ).order_by(desc(Resume.created_at)).first()
        
    #     # Extract skills
    #     job_skills = job.skills.split(",") if isinstance(job.skills, str) and job.skills else []
    #     candidate_skills = [skill.skill_name for skill in candidate.skills]
        
    #     # Calculate skill-level matching
    #     skills_match = {}
    #     for job_skill in job_skills:
    #         skill_name = job_skill.strip().lower()
    #         if not skill_name:
    #             continue
                
    #         # Check for exact match
    #         if any(cs.lower() == skill_name for cs in candidate_skills):
    #             skills_match[skill_name] = 1.0
    #         # Check for partial match (candidate skill contains job skill or vice versa)
    #         elif any(cs.lower() in skill_name or skill_name in cs.lower() for cs in candidate_skills):
    #             skills_match[skill_name] = 0.5
    #         else:
    #             skills_match[skill_name] = 0.0
        
    #     # Calculate overall match score based on skills
    #     skill_match_score = 0
    #     if skills_match:
    #         skill_match_score = sum(skills_match.values()) / len(skills_match) * 100
        
    #     # Prepare report
    #     report = {
    #         "job_id": job.id,
    #         "job_title": job.title,
    #         "candidate_id": candidate.id,
    #         "candidate_name": f"{candidate.first_name} {candidate.last_name}".strip(),
    #         "skills_match": skills_match,
    #         "match_score": skill_match_score
    #     }
        
    #     # Enhance with LLM analysis if resume text available
    #     if resume and (hasattr(resume, 'parsed_text') and resume.parsed_text) and llm_service:
    #         resume_text = resume.parsed_text
            
    #         # If parsed_text doesn't exist, try parsed_content as fallback
    #         if not resume_text and hasattr(resume, 'parsed_content') and resume.parsed_content:
    #             resume_text = resume.parsed_content
                
    #         if resume_text:
    #             job_description = f"""
    #             Title: {job.title}
    #             Department: {job.department}
    #             Location: {job.location}
    #             Description: {job.description or ''}
    #             Requirements: {job.requirements or ''}
    #             """
                
    #             # Generate in-depth analysis
    #             analysis_prompt = f"""
    #             You are an expert AI recruiter. Provide a detailed analysis of how well the candidate matches the job.
                
    #             JOB:
    #             {job_description}
                
    #             JOB SKILLS NEEDED:
    #             {', '.join(job_skills) if job_skills else 'Not specified'}
                
    #             CANDIDATE:
    #             Name: {candidate.first_name} {candidate.last_name}
    #             Skills: {', '.join(candidate_skills) if candidate_skills else 'Not specified'}
                
    #             RESUME:
    #             {resume_text[:3000]}  # Use first 3000 chars to avoid token limits
                
    #             Please provide:
    #             1. An overall match score (0-100)
    #             2. A detailed analysis of strengths and weaknesses
    #             3. Why this person would be a good fit or what they're missing
    #             4. Recommendations for interviewing this candidate
                
    #             Format as a structured analysis with clear sections.
    #             """
                
    #             try:
    #                 # Use mixtral instead of mistral (ensure model name is correct)
    #                 explanation = await llm_service.generate_text_async(
    #                     analysis_prompt, 
    #                     model="mixtral",  # Use more capable model for detailed analysis
    #                     max_tokens=800
    #                 )
    #             except Exception as e:
    #                 logger.error(f"Error generating text with LLM: {str(e)}")
    #                 explanation = f"Error generating detailed analysis. Basic skill matching score: {skill_match_score:.1f}%"
                
    #             # Extract LLM's match score from the explanation if possible
    #             import re
    #             score_match = re.search(r'(\d{1,3})(?:/100|%)', explanation)
    #             if score_match:
    #                 llm_score = float(score_match.group(1))
    #                 # Average with skill match score
    #                 report["match_score"] = (skill_match_score + llm_score) / 2
                
    #             report["explanation"] = explanation.strip()
        
    #     return report
    # except Exception as e:
    #     logger.exception(f"Error generating match report: {str(e)}")
    #     raise HTTPException(status_code=500, detail=str(e))
