"""
Integration module for the enhanced matching capabilities.
This module demonstrates how to use the MatchingEnhancer with existing services.
"""

import logging
from typing import List, Dict, Any, Optional

from .matching_enhancer import MatchingEnhancer
from .rag_service import RAGService

logger = logging.getLogger(__name__)

class MatchingIntegrator:
    """Integrates advanced matching capabilities with existing services."""
    
    def __init__(self, rag_service: RAGService):
        """
        Initialize the matching integrator.
        
        Args:
            rag_service: The RAG service instance for database access
        """
        self.rag_service = rag_service
        self.enhancer = MatchingEnhancer(embedding_model=rag_service.embedding_adapter)
    
    async def enhanced_candidate_job_matching(self, job_id: int, db, min_score: float = 20.0, limit: int = 10):
        """
        Find candidates matching a job with enhanced scoring and explanations.
        
        Args:
            job_id: ID of the job to match candidates against
            db: Database session
            min_score: Minimum match score threshold
            limit: Maximum number of candidates to return
            
        Returns:
            List of candidates with enhanced match data
        """
        from backend.models.models import Job, Candidate, Resume, Skill
        from sqlalchemy import desc
        
        # Get the job details
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning(f"Job with ID {job_id} not found")
            return []
            
        # Get all candidates with skills
        candidates = db.query(Candidate).all()
        if not candidates:
            logger.warning("No candidates found in database")
            return []
            
        # Prepare job data
        job_title = job.title or ""
        job_description = job.job_overview or ""
        job_requirements = job.required_qualifications or ""
        job_skills = job.skills if job.skills else []
        
        # Normalize job skills list
        if isinstance(job_skills, str):
            job_skills = [s.strip() for s in job_skills.split(",") if s.strip()]
            
        # Extract job experience level
        job_text = f"{job_title} {job_requirements}"
        job_level, job_years = self.enhancer.extract_experience_level(job_text)
        logger.info(f"Job {job_id} experience level: {job_level} ({job_years} years)")
        
        # Process each candidate
        matches = []
        for candidate in candidates:
            # Get candidate skills and profile information
            candidate_skills = [skill.skill_name for skill in candidate.skills] if hasattr(candidate, 'skills') and candidate.skills else []
            
            # Get candidate position/experience
            candidate_position = candidate.current_position or ""
            
            # Calculate component scores
            
            # 1. Skill match
            skill_score, matching_skills = self.enhancer.calculate_skill_match_score(
                job_skills, candidate_skills
            )
            
            # Apply cross-domain skill penalty for incompatible roles
            original_skill_score = skill_score
            skill_score = self.enhancer.apply_cross_domain_skill_penalty(
                skill_score, job_title, candidate_position
            )
            
            # Log skill penalty application
            if original_skill_score != skill_score:
                logger.info(f"[MatchIntegratorDebug] Cross-domain skill penalty applied to candidate {candidate.id}: {original_skill_score:.1f}% → {skill_score:.1f}%")
            
            # 2. Role match
            role_score = self.enhancer.calculate_role_match_score(
                job_title, job_description, candidate_position
            )
            
            # 3. Experience match
            candidate_level, candidate_years = self.enhancer.extract_experience_level(candidate_position)
            experience_score = self.enhancer.calculate_experience_match_score(
                job_level, job_years, candidate_level, candidate_years
            )
            
            # Enhanced debugging for score calculation
            logger.debug(f"[MatchIntegratorDebug] Candidate {candidate.id} ({candidate.first_name} {candidate.last_name}) - Position: '{candidate_position}'")
            logger.debug(f"[MatchIntegratorDebug] Component scores - Role: {role_score:.1f}%, Skill: {skill_score:.1f}%, Experience: {experience_score:.1f}%")
            
            # Calculate combined score with MORE AGGRESSIVE weighting
            # Prioritize role match more heavily for better filtering
            if role_score < 30:  # Even more aggressive threshold (was 25)
                # Apply SEVERE penalty for fundamentally incompatible roles
                match_score = (
                    skill_score * 0.15 +  # Further reduce skill importance for bad role fits
                    role_score * 0.7 +   # Emphasize the poor role match even more
                    experience_score * 0.15  # Reduced weight for experience when role doesn't fit
                ) * 0.25  # Even MORE SEVERE overall penalty (was 0.3)
                logger.info(f"[MatchIntegratorDebug] SEVERE role mismatch penalty applied to candidate {candidate.id}: final score = {match_score:.1f}%")
            elif role_score < 50:  # Increased threshold to catch more mismatches (was 40)
                # Apply moderate penalty for poor role matches
                match_score = (
                    skill_score * 0.2 +
                    role_score * 0.6 +
                    experience_score * 0.2
                ) * 0.45  # More aggressive penalty (was 0.6)
                logger.info(f"[MatchIntegratorDebug] Moderate role mismatch penalty applied to candidate {candidate.id}: final score = {match_score:.1f}%")
            else:
                # Standard weighting for reasonable role matches
                match_score = (
                    skill_score * 0.35 +
                    role_score * 0.45 +  # Increased role importance
                    experience_score * 0.2  # Reduced experience weight
                )
                logger.debug(f"[MatchIntegratorDebug] Standard scoring applied to candidate {candidate.id}: final score = {match_score:.1f}%")
            
            # Additional cross-domain final penalty check - MORE AGGRESSIVE
            if role_score < 50 and skill_score < 60:  # Broadened criteria
                # Apply additional penalty for cross-domain matches
                match_score *= 0.4  # More aggressive (was 0.5)
                logger.info(f"[MatchIntegratorDebug] Additional cross-domain penalty for role/skill mismatch: candidate {candidate.id}, final score = {match_score:.1f}%")
            
            # Generate detailed explanation
            match_explanation = self.enhancer.generate_match_explanation(
                job, candidate, matching_skills, role_score, skill_score, experience_score
            )
            
            # Include candidate if score meets threshold
            if match_score >= min_score:
                # Get most recent resume
                resume = db.query(Resume).filter(
                    Resume.candidate_id == candidate.id
                ).order_by(desc(Resume.created_at)).first()
                
                # Create match result
                match_data = {
                    "id": candidate.id,
                    "name": f"{candidate.first_name or ''} {candidate.last_name or ''}".strip() or "Unknown",
                    "email": candidate.email or "",
                    "resume_id": resume.id if resume else None,
                    "skills": candidate_skills,
                    "position": candidate_position,
                    "experience_level": candidate_level,
                    "years_experience": candidate_years,
                    "skill_match_score": skill_score,
                    "role_match_score": role_score,
                    "experience_match_score": experience_score,
                    "match_score": match_score,
                    "match_explanation": match_explanation,
                    "source": "enhanced_match"
                }
                
                matches.append(match_data)
        
        # Sort by match score and limit results
        sorted_matches = sorted(matches, key=lambda x: x.get("match_score", 0), reverse=True)
        return sorted_matches[:limit]
    
    async def enhanced_job_candidate_matching(self, candidate_id: str, db, min_score: float = 20.0, limit: int = 10):
        """
        Find jobs matching a candidate with enhanced scoring and explanations.
        
        Args:
            candidate_id: ID of the candidate to match jobs against
            db: Database session
            min_score: Minimum match score threshold
            limit: Maximum number of jobs to return
            
        Returns:
            List of jobs with enhanced match data
        """
        from backend.models.models import Job, Candidate, Resume, Skill
        from sqlalchemy import desc
        
        # Get the candidate details
        candidate = db.query(Candidate).filter(Candidate.id == str(candidate_id)).first()
        if not candidate:
            logger.warning(f"Candidate with ID {candidate_id} not found")
            return []
            
        # Get all jobs
        jobs = db.query(Job).all()
        if not jobs:
            logger.warning("No jobs found in database")
            return []
            
        # Prepare candidate data
        candidate_skills = [skill.skill_name for skill in candidate.skills] if hasattr(candidate, 'skills') and candidate.skills else []
        candidate_position = candidate.current_position or ""
        
        # Extract candidate experience level
        candidate_level, candidate_years = self.enhancer.extract_experience_level(candidate_position)
        logger.info(f"Candidate {candidate_id} experience level: {candidate_level} ({candidate_years} years)")
        
        # Process each job
        matches = []
        for job in jobs:
            # Get job skills
            job_skills = job.skills if job.skills else []
            if isinstance(job_skills, str):
                job_skills = [s.strip() for s in job_skills.split(",") if s.strip()]
                
            # Get job details
            job_title = job.title or ""
            job_description = job.job_overview or ""
            job_requirements = job.required_qualifications or ""
            
            # Extract job experience level
            job_text = f"{job_title} {job_requirements}"
            job_level, job_years = self.enhancer.extract_experience_level(job_text)
            
            # Calculate component scores
            
            # 1. Skill match
            skill_score, matching_skills = self.enhancer.calculate_skill_match_score(
                job_skills, candidate_skills
            )
            
            # Apply cross-domain skill penalty for incompatible roles
            original_skill_score = skill_score
            skill_score = self.enhancer.apply_cross_domain_skill_penalty(
                skill_score, job_title, candidate_position
            )
            
            # Log skill penalty application
            if original_skill_score != skill_score:
                logger.info(f"[JobMatchDebug] Cross-domain skill penalty applied for job {job.id}: {original_skill_score:.1f}% → {skill_score:.1f}%")
            
            # 2. Role match
            role_score = self.enhancer.calculate_role_match_score(
                job_title, job_description, candidate_position
            )
            
            # 3. Experience match
            experience_score = self.enhancer.calculate_experience_match_score(
                job_level, job_years, candidate_level, candidate_years
            )
            
            # Enhanced debugging for score calculation
            logger.debug(f"[JobMatchDebug] Job {job.id} ('{job.title}') vs Candidate {candidate_id}")
            logger.debug(f"[JobMatchDebug] Component scores - Role: {role_score:.1f}%, Skill: {skill_score:.1f}%, Experience: {experience_score:.1f}%")
            
            # Calculate combined score with MORE AGGRESSIVE weighting (same as candidate matching)
            if role_score < 30:  # Even more aggressive threshold
                # Apply SEVERE penalty for fundamentally incompatible roles
                match_score = (
                    skill_score * 0.15 +  # Further reduce skill importance for bad role fits
                    role_score * 0.7 +   # Emphasize the poor role match even more
                    experience_score * 0.15  # Reduced weight for experience when role doesn't fit
                ) * 0.25  # Even MORE SEVERE overall penalty
                logger.info(f"[JobMatchDebug] SEVERE role mismatch penalty applied for job {job.id}: final score = {match_score:.1f}%")
            elif role_score < 50:  # Increased threshold to catch more mismatches
                # Apply moderate penalty for poor role matches
                match_score = (
                    skill_score * 0.2 +
                    role_score * 0.6 +
                    experience_score * 0.2
                ) * 0.45  # More aggressive penalty
                logger.info(f"[JobMatchDebug] Moderate role mismatch penalty applied for job {job.id}: final score = {match_score:.1f}%")
            else:
                # Standard weighting for reasonable role matches
                match_score = (
                    skill_score * 0.35 +
                    role_score * 0.45 +  # Increased role importance
                    experience_score * 0.2  # Reduced experience weight
                )
                logger.debug(f"[JobMatchDebug] Standard scoring applied for job {job.id}: final score = {match_score:.1f}%")
            
            # Additional cross-domain final penalty check - MORE AGGRESSIVE
            if role_score < 50 and skill_score < 60:  # Broadened criteria
                # Apply additional penalty for cross-domain matches
                match_score *= 0.4  # More aggressive
                logger.info(f"[JobMatchDebug] Additional cross-domain penalty for role/skill mismatch: job {job.id}, final score = {match_score:.1f}%")
            
            # Generate detailed explanation
            match_explanation = self.enhancer.generate_match_explanation(
                job, candidate, matching_skills, role_score, skill_score, experience_score
            )
            
            # Include job if score meets threshold
            if match_score >= min_score:
                match_data = {
                    "id": job.id,
                    "title": job.title,
                    "department": job.department if hasattr(job, 'department') else None,
                    "description": job.job_overview,
                    "location": job.location if hasattr(job, 'location') else None,
                    "skills": job_skills,
                    "skill_match_score": skill_score,
                    "role_match_score": role_score,
                    "experience_match_score": experience_score,
                    "match_score": match_score,
                    "match_explanation": match_explanation
                }
                
                matches.append(match_data)
        
        # Sort by match score and limit results
        sorted_matches = sorted(matches, key=lambda x: x.get("match_score", 0), reverse=True)
        return sorted_matches[:limit]
    
    async def find_similar_jobs(self, job_id: int, db, limit: int = 5):
        """
        Find jobs similar to the specified job with enhanced similarity metrics.
        
        Args:
            job_id: ID of the job to find similar jobs for
            db: Database session
            limit: Maximum number of similar jobs to return
            
        Returns:
            List of similar jobs with similarity scores and explanations
        """
        from backend.models.models import Job
        
        # Get the target job
        target_job = db.query(Job).filter(Job.id == job_id).first()
        if not target_job:
            logger.warning(f"Job with ID {job_id} not found")
            return []
            
        # Get all other jobs
        other_jobs = db.query(Job).filter(Job.id != job_id).all()
        if not other_jobs:
            logger.warning("No other jobs found in database")
            return []
            
        # Calculate similarity between target job and each other job
        similarities = []
        for job in other_jobs:
            similarity_score, similarity_explanation = self.enhancer.calculate_job_similarity(
                target_job, job
            )
            
            similarities.append({
                "job": job,
                "score": similarity_score,
                "explanation": similarity_explanation
            })
        
        # Sort by similarity score and limit results
        sorted_similarities = sorted(similarities, key=lambda x: x.get("score", 0), reverse=True)
        limited_similarities = sorted_similarities[:limit]
        
        # Format results
        similar_jobs = [
            {
                "id": item["job"].id,
                "title": item["job"].title,
                "department": item["job"].department if hasattr(item["job"], 'department') else None,
                "location": item["job"].location if hasattr(item["job"], 'location') else None,
                "skills": item["job"].skills,
                "similarity_score": item["score"],
                "similarity_explanation": item["explanation"]
            }
            for item in limited_similarities
        ]
        
        return similar_jobs
