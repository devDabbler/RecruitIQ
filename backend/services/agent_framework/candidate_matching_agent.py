from typing import Dict
from backend.services.agent_framework.base_agent import BaseAgent
from backend.services.matching_service import MatchingService
from backend.services.matching_integrator import MatchingIntegrator
from backend.services.rag_service import RAGService
from backend.services.llm_service import get_llm_service
from backend.services.graph_service import get_graph_service
from backend.utils.config import get_settings

class CandidateMatchingAgent(BaseAgent):
    """Agentic zero implementation for candidate matching"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize services here. This is a temporary solution until a proper
        # dependency injection mechanism for agents is implemented.
        settings = get_settings()
        llm_service = get_llm_service()
        graph_service = get_graph_service()
        rag_service = RAGService(llm_service, graph_service, settings)
        
        self.matching_service = MatchingService()
        self.matching_integrator = MatchingIntegrator(rag_service=rag_service)

    async def execute(self, task: Dict) -> list:
        """
        Execute the matching task based on the specified type and strategy.
        
        Args:
            task: A dictionary containing task details.
                  
        Returns:
            A list of matching results.
        """
        task_type = task.get("type", "candidates_for_job")
        db = task.get("db")

        if not db:
            raise ValueError("A 'db' session is required for all tasks.")

        if task_type == "candidates_for_job":
            strategy = task.get("strategy", "basic")
            job_id = task.get("job_id")
            if not job_id:
                raise ValueError("'job_id' is required for the 'candidates_for_job' task.")
            
            if strategy == "enhanced":
                return await self.matching_integrator.enhanced_candidate_job_matching(
                    job_id=job_id,
                    db=db,
                    min_score=task.get("min_score", 30.0),
                    limit=task.get("limit", 10)
                )
            else: # basic strategy
                return await self.matching_service.match_candidates(
                    job_id=job_id,
                    db=db
                )
        
        elif task_type == "jobs_for_candidate":
            candidate_id = task.get("candidate_id")
            if not candidate_id:
                raise ValueError("'candidate_id' is required for the 'jobs_for_candidate' task.")
            
            return await self.matching_integrator.enhanced_job_candidate_matching(
                candidate_id=candidate_id,
                db=db,
                min_score=task.get("min_score", 30.0),
                limit=task.get("limit", 10)
            )

        elif task_type == "similar_jobs":
            job_id = task.get("job_id")
            if not job_id:
                raise ValueError("'job_id' is required for the 'similar_jobs' task.")

            return await self.matching_integrator.find_similar_jobs(
                job_id=job_id,
                db=db,
                limit=task.get("limit", 5)
            )
        
        else:
            raise ValueError(f"Unknown task type: '{task_type}'")
