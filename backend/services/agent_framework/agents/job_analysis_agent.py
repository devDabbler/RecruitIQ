from typing import Any, Dict, Optional
import logging
import json
import re
from sqlalchemy.orm import Session

from backend.services.agent_framework.base_agent import BaseAgent
from backend.services.agent_framework.agent_registry import register
from backend.services.job_service import JobService
from backend.services.llm_service import LLMService
from backend.models.models import Job

logger = logging.getLogger(__name__)

@register(
    name="JobAnalysisAgent",
    description="Performs deep analysis of job descriptions, including quality scoring and market comparison."
)
class JobAnalysisAgent(BaseAgent):
    """Analyzes job descriptions and requirements using LLM and graph-based insights."""

    def __init__(self, job_service: JobService, llm_service: LLMService):
        self.job_service = job_service
        self.llm_service = llm_service

    async def execute(self, task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        job_id = task.get("job_id")
        job_data = task.get("job_data")
        db: Optional[Session] = task.get("db")
        action = task.get("action", "analyze")  # Default action is analyze

        if not job_id and not job_data:
            return {"status": "error", "message": "Task must include 'job_id' or 'job_data'."}

        if job_id and not db:
            return {"status": "error", "message": "'db' session is required when using 'job_id'."}

        try:
            # Handle match report generation
            if action == "generate_match_report":
                return await self._generate_match_report(task)
            
            # Handle regular job analysis
            if job_id:
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job:
                    return {"status": "error", "message": f"Job with ID {job_id} not found."}
                job_data = {c.name: getattr(job, c.name) for c in job.__table__.columns}

            logger.info(f"Starting analysis for job: {job_data.get('title', 'N/A')}")

            quality_assessment = await self._assess_job_quality(job_data)
            market_comparison = await self._compare_to_market(job_data)

            return {
                "status": "completed",
                "job_title": job_data.get("title"),
                "analysis": {
                    "quality_assessment": quality_assessment,
                    "market_comparison": market_comparison,
                }
            }
        except Exception as e:
            logger.exception(f"Error during job analysis for job_id {job_id}: {e}")
            return {"status": "error", "message": str(e)}

    async def _assess_job_quality(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Uses an LLM to assess the quality of the job description."""
        logger.info("Assessing job description quality.")
        description = self.job_service._prepare_description_text(job_data)
        requirements = self.job_service._prepare_requirements_text(job_data)

        prompt = f"""
        Act as an expert recruitment consultant. Analyze the following job description for quality.
        Provide a JSON object with scores (1-10) for 'clarity', 'inclusivity', and 'realism'.
        Also, provide a 'feedback' string (2-3 sentences) with actionable advice for improvement.

        - clarity: Is the language clear, concise, and free of jargon?
        - inclusivity: Does the language appeal to a diverse range of candidates?
        - realism: Are the requirements and expectations realistic for the role?

        Job Details:
        --- 
        {description}
        {requirements}
        ---

        Return ONLY the JSON object.
        """
        try:
            response_msg = await self.llm_service.generate_text_async(prompt, max_tokens=300)
            response_text = response_msg.content if hasattr(response_msg, 'content') else str(response_msg)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            logger.warning("Could not parse JSON from job quality assessment response.")
            return {"error": "Failed to parse LLM response."}
        except Exception as e:
            logger.error(f"LLM call for job quality assessment failed: {e}")
            return {"error": str(e)}

    async def _compare_to_market(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compares the job's required skills to the broader market."""
        title = job_data.get("title")
        if not title:
            return {"error": "Job title is required for market comparison."}

        logger.info(f"Comparing job '{title}' to the market.")
        try:
            job_skills = set(job_data.get("skills", []))
            market_skills = set(await self.job_service.get_skills_for_comparable_jobs(title))

            return {
                "job_skills": sorted(list(job_skills)),
                "market_skills": sorted(list(market_skills)),
                "matching_skills": sorted(list(job_skills.intersection(market_skills))),
                "missing_from_job": sorted(list(market_skills.difference(job_skills))),
            }
        except Exception as e:
            logger.error(f"Market comparison failed for job '{title}': {e}")
            return {"error": str(e)}

    async def _generate_match_report(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a detailed match report between a job and candidate"""
        job_id = task.get("job_id")
        candidate_id = task.get("candidate_id")
        db = task.get("db")
        
        if not job_id or not candidate_id or not db:
            return {"status": "error", "message": "Missing required parameters: job_id, candidate_id, and db"}
        
        try:
            # Import models here to avoid circular imports
            from backend.models.models import Job, Candidate, Resume
            
            # Get job and candidate data
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {"status": "error", "message": f"Job with ID {job_id} not found"}
            
            # Handle both string and int candidate IDs
            candidate = db.query(Candidate).filter(Candidate.id == str(candidate_id)).first()
            if not candidate:
                return {"status": "error", "message": f"Candidate with ID {candidate_id} not found"}
            
            # Get the most recent resume for detailed analysis
            resume = db.query(Resume).filter(
                Resume.candidate_id == candidate.id
            ).order_by(Resume.created_at.desc()).first()
            
            logger.info(f"Generating match report for job '{job.title}' and candidate '{candidate.first_name} {candidate.last_name}'")
            
            # Extract job skills
            job_skills = []
            if hasattr(job, 'skills') and job.skills:
                if isinstance(job.skills, str):
                    job_skills = [skill.strip().lower() for skill in job.skills.split(",") if skill.strip()]
                elif isinstance(job.skills, list):
                    job_skills = [skill.lower() for skill in job.skills]
            
            # Extract candidate skills
            candidate_skills = []
            if hasattr(candidate, 'skills') and candidate.skills:
                candidate_skills = [skill.skill_name.lower() for skill in candidate.skills]
            
            # Calculate skill matching
            skills_match = {}
            if job_skills:
                for job_skill in job_skills:
                    skill_name = job_skill.strip().lower()
                    if not skill_name:
                        continue
                    
                    # Check for exact match
                    if skill_name in candidate_skills:
                        skills_match[skill_name] = 1.0
                    # Check for partial match
                    elif any(skill_name in cs or cs in skill_name for cs in candidate_skills):
                        skills_match[skill_name] = 0.6
                    else:
                        skills_match[skill_name] = 0.0
            
            # Calculate overall skill match score
            skill_match_score = 0
            if skills_match:
                skill_match_score = sum(skills_match.values()) / len(skills_match) * 100
            
            # Calculate experience match
            job_min_exp = getattr(job, 'min_years_experience', 0) or 0
            candidate_exp = getattr(candidate, 'experience_years', 0) or 0
            
            experience_match_score = 100  # Default to perfect match
            if job_min_exp > 0 and candidate_exp > 0:
                if candidate_exp >= job_min_exp:
                    experience_match_score = 100
                elif candidate_exp >= job_min_exp * 0.8:
                    experience_match_score = 85
                elif candidate_exp >= job_min_exp * 0.6:
                    experience_match_score = 70
                else:
                    experience_match_score = 50
            
            # Calculate role match based on job title similarity
            job_title = job.title.lower()
            candidate_position = getattr(candidate, 'current_position', '') or getattr(candidate, 'position', '') or ''
            candidate_position = candidate_position.lower()
            
            role_match_score = 50  # Default moderate match
            if candidate_position and job_title:
                # Simple keyword matching for role similarity
                job_keywords = set(job_title.split())
                candidate_keywords = set(candidate_position.split())
                
                common_keywords = job_keywords.intersection(candidate_keywords)
                if common_keywords:
                    role_match_score = min(90, 50 + len(common_keywords) * 15)
                elif any(keyword in job_title for keyword in candidate_keywords):
                    role_match_score = 70
                elif any(keyword in candidate_position for keyword in job_keywords):
                    role_match_score = 70
            
            # Calculate overall match score
            overall_match_score = (
                skill_match_score * 0.4 +
                experience_match_score * 0.3 +
                role_match_score * 0.3
            )
            
            # Generate LLM-powered explanation if available
            explanation = await self._generate_match_explanation(
                job, candidate, resume, overall_match_score, 
                skill_match_score, experience_match_score, role_match_score
            )
            
            # Prepare the match report
            report = {
                "job_id": job.id,
                "job_title": job.title,
                "candidate_id": candidate.id,
                "candidate_name": f"{candidate.first_name} {candidate.last_name}".strip(),
                "match_score": round(overall_match_score, 1),
                "skill_score": round(skill_match_score, 1),
                "experience_score": round(experience_match_score, 1),
                "role_score": round(role_match_score, 1),
                "skills_match": skills_match,
                "explanation": explanation,
                "status": "completed"
            }
            
            return report
            
        except Exception as e:
            logger.exception(f"Error generating match report: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _generate_match_explanation(self, job, candidate, resume, overall_score, 
                                        skill_score, exp_score, role_score) -> str:
        """Generate LLM-powered explanation of the match"""
        try:
            # Build context for LLM analysis
            job_description = f"""
            Title: {job.title}
            Department: {getattr(job, 'department', 'Not specified')}
            Location: {getattr(job, 'location', 'Not specified')}
            Description: {getattr(job, 'description', '') or getattr(job, 'job_overview', '')}
            Requirements: {getattr(job, 'requirements', '')}
            """
            
            candidate_info = f"""
            Name: {candidate.first_name} {candidate.last_name}
            Current Position: {getattr(candidate, 'current_position', 'Not specified')}
            Company: {getattr(candidate, 'current_company', 'Not specified')}
            Experience: {getattr(candidate, 'experience_years', 'Not specified')} years
            Skills: {', '.join([skill.skill_name for skill in candidate.skills]) if hasattr(candidate, 'skills') and candidate.skills else 'Not specified'}
            """
            
            resume_text = ""
            if resume and hasattr(resume, 'full_text') and resume.full_text:
                resume_text = resume.full_text[:2000]  # Limit to avoid token limits
            
            prompt = f"""
            As an expert recruiter, analyze this job-candidate match and provide a clear, professional explanation.
            
            JOB:
            {job_description}
            
            CANDIDATE:
            {candidate_info}
            
            RESUME EXCERPT:
            {resume_text}
            
            MATCH SCORES:
            - Overall: {overall_score:.1f}%
            - Skills: {skill_score:.1f}%
            - Experience: {exp_score:.1f}%
            - Role Fit: {role_score:.1f}%
            
            Provide a 2-3 sentence professional analysis explaining:
            1. The candidate's key strengths for this role
            2. Any potential concerns or gaps
            3. Overall recommendation (Strong/Good/Moderate/Poor fit)
            
            Keep it concise and actionable for hiring managers.
            """
            
            response = await self.llm_service.generate_text_async(
                prompt, 
                model="mixtral",  # Use capable model
                max_tokens=400
            )
            
            # Extract text from response
            if hasattr(response, 'content'):
                return response.content.strip()
            else:
                return str(response).strip()
                
        except Exception as e:
            logger.error(f"Error generating LLM explanation: {e}")
            # Provide fallback explanation
            if overall_score >= 80:
                return f"Strong candidate match ({overall_score:.1f}%). Excellent alignment in key areas with {skill_score:.1f}% skill match and {exp_score:.1f}% experience fit. Recommend proceeding with interview."
            elif overall_score >= 60:
                return f"Good candidate potential ({overall_score:.1f}%). Solid foundation with {skill_score:.1f}% skill match. Some areas may need development but worth considering for screening."
            elif overall_score >= 40:
                return f"Moderate fit ({overall_score:.1f}%). Mixed results with {skill_score:.1f}% skill alignment. Requires careful evaluation to determine suitability."
            else:
                return f"Limited match ({overall_score:.1f}%). Significant gaps in required areas. May not be suitable for this specific role."
