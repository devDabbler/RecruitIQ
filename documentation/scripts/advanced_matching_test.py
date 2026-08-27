"""
Script to run advanced candidate-job matching for ALL jobs and ALL candidates in the backend database.
Outputs all candidate scores and match explanations for each job.
"""
import os
import sys
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.utils.database import SessionLocal
from backend.services.rag_service import RAGService
from backend.services.matching_integrator import MatchingIntegrator
from backend.models.models import Job


def main():
    session = SessionLocal()
    from backend.services.llm_service import get_llm_service
    from backend.services.graph_service import get_graph_service
    from backend.utils.config import get_settings

    settings = get_settings()
    llm_service = get_llm_service(settings)
    graph_service = get_graph_service()
    rag_service = RAGService(llm_service, graph_service, settings)
    integrator = MatchingIntegrator(rag_service)

    jobs = session.query(Job).all()
    if not jobs:
        print("No jobs found in the database.")
        return

    async def run_matching():
        for job in jobs:
            print(f"\n=== Job: [{job.id}] {job.title} ===")
            matches = await integrator.enhanced_candidate_job_matching(job_id=job.id, db=session, min_score=0, limit=1000)
            if not matches:
                print("No candidates matched.")
                continue
            for match in matches:
                print(f"Candidate: [{match.get('id')}] {match.get('first_name')} {match.get('last_name')}")
                print(f"  Match Score: {match.get('match_score'):.2f}")
                print(f"  Skill Score: {match.get('skill_match_score'):.2f} | Role Score: {match.get('role_match_score'):.2f} | Experience Score: {match.get('experience_match_score'):.2f}")
                print(f"  Explanation: {match.get('match_explanation')}")
                print("-")
    
    asyncio.run(run_matching())
    session.close()

if __name__ == "__main__":
    main()
