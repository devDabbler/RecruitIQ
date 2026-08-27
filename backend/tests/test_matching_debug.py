#!/usr/bin/env python3
"""
Debug script to test candidate-job matching
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.utils.database import get_db
from backend.services.matching_integrator import MatchingIntegrator
from backend.services.rag_service import RAGService
from backend.services.llm_service import LLMService
from backend.services.graph_service import GraphService
from backend.utils.config import get_settings
from backend.models.models import Job, Candidate

async def test_matching():
    db = next(get_db())
    
    # Get all jobs and candidates
    jobs = db.query(Job).all()
    candidates = db.query(Candidate).all()
    
    print(f'Found {len(jobs)} jobs and {len(candidates)} candidates')
    
    for job in jobs:
        print(f'\nJob {job.id}: {job.title}')
        print(f'Skills: {job.skills}')
        if job.required_qualifications:
            print(f'Requirements: {job.required_qualifications[:100]}...')
    
    for candidate in candidates:
        print(f'\nCandidate {candidate.id}: {candidate.first_name} {candidate.last_name}')
        print(f'Position: {candidate.current_position}')
        skills = [s.skill_name for s in candidate.skills] if candidate.skills else []
        print(f'Skills: {skills}')
    
    # Test matching for job 18 (data scientist)
    if jobs:
        job_id = 18
        settings = get_settings()
        llm_service = LLMService(settings)
        graph_service = GraphService()
        rag_service = RAGService(llm_service, graph_service, settings)
        integrator = MatchingIntegrator(rag_service)
        
        matches = await integrator.enhanced_candidate_job_matching(
            job_id=job_id, 
            db=db, 
            min_score=20.0, 
            limit=10
        )
        
        print(f'\n=== MATCHING RESULTS FOR JOB {job_id} ===')
        for match in matches:
            print(f'{match["name"]}: {match["match_score"]:.1f}% (Role: {match["role_match_score"]:.1f}%, Skill: {match["skill_match_score"]:.1f}%, Exp: {match["experience_match_score"]:.1f}%)')
            print(f'  Position: {match["position"]}')
            print(f'  Skills: {match["skills"]}')

if __name__ == "__main__":
    asyncio.run(test_matching()) 