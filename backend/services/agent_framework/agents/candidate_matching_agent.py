from typing import Any, Dict, Optional
import logging
from sqlalchemy.orm import Session

from backend.services.agent_framework.base_agent import BaseAgent
from backend.services.agent_framework.agent_registry import register
from backend.services.matching_integrator import MatchingIntegrator

logger = logging.getLogger(__name__)

@register(
    name="CandidateMatchingAgent",
    description="Handles intelligent candidate-job matching workflows, including semantic and graph-based analysis."
)
class CandidateMatchingAgent(BaseAgent):
    """Handles intelligent candidate-job matching workflows."""

    def __init__(self, matching_integrator: MatchingIntegrator):
        self.matching_integrator = matching_integrator

    async def execute(self, task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Executes a matching task based on the specified type and strategy.
        
        Args:
            task: A dictionary containing task details, including:
                  - 'type' (str): The task type ('candidates_for_job', 'jobs_for_candidate', 'similar_jobs')
                  - 'job_id' (int): The ID of the job (for candidates_for_job and similar_jobs)
                  - 'candidate_id' (str): The ID of the candidate (for jobs_for_candidate)
                  - 'strategy' (str): The matching strategy ('enhanced' or 'basic')
                  - 'db' (Session): The database session
                  - 'min_score' (float, optional): The minimum match score
                  - 'limit' (int, optional): The max number of results to return
        
        Returns:
            A dictionary with the matching results.
        """
        task_type = task.get("type", "candidates_for_job")
        db: Optional[Session] = task.get("db")

        if not db:
            logger.error("CandidateMatchingAgent missing required parameter: db session.")
            return {"status": "error", "message": "Missing required parameter: 'db'."}

        logger.info(f"Executing matching task type '{task_type}'.")

        try:
            if task_type == "candidates_for_job":
                return await self._handle_candidates_for_job(task)
            elif task_type == "jobs_for_candidate":
                return await self._handle_jobs_for_candidate(task)
            elif task_type == "similar_jobs":
                return await self._handle_similar_jobs(task)
            else:
                logger.warning(f"Unknown task type: {task_type}")
                return {"status": "error", "message": f"Unknown task type: {task_type}"}

        except Exception as e:
            logger.exception(f"An error occurred during matching task '{task_type}': {e}")
            return {"status": "error", "message": str(e), "task_type": task_type}

    async def _handle_candidates_for_job(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle finding candidates for a job."""
        job_id = task.get("job_id")
        strategy = task.get("strategy", "enhanced")
        db = task.get("db")

        if not job_id:
            return {"status": "error", "message": "Missing required parameter: 'job_id' for candidates_for_job task."}

        logger.info(f"Finding candidates for job_id {job_id} with strategy '{strategy}'.")

        if strategy == "enhanced":
            min_score = task.get("min_score", 40.0)
            limit = task.get("limit", 15)
            matches = await self.matching_integrator.enhanced_candidate_job_matching(
                job_id=job_id, db=db, min_score=min_score, limit=limit
            )
            return {
                "status": "completed",
                "strategy": "enhanced",
                "job_id": job_id,
                "match_count": len(matches) if isinstance(matches, list) else len(matches.get("matches", [])),
                "results": matches,
            }
        elif strategy == "basic":
            logger.warning("Basic matching strategy is not yet implemented.")
            return {"status": "not_implemented", "message": "Basic matching strategy not implemented."}
        else:
            return {"status": "error", "message": f"Unknown matching strategy: {strategy}"}

    async def _handle_jobs_for_candidate(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle finding jobs for a candidate."""
        candidate_id = task.get("candidate_id")
        db = task.get("db")

        if not candidate_id:
            return {"status": "error", "message": "Missing required parameter: 'candidate_id' for jobs_for_candidate task."}

        logger.info(f"Finding jobs for candidate_id {candidate_id}.")

        min_score = task.get("min_score", 30.0)
        limit = task.get("limit", 10)
        matches = await self.matching_integrator.enhanced_job_candidate_matching(
            candidate_id=candidate_id, db=db, min_score=min_score, limit=limit
        )
        return {
            "status": "completed",
            "candidate_id": candidate_id,
            "match_count": len(matches) if isinstance(matches, list) else len(matches.get("matches", [])),
            "results": matches,
        }

    async def _handle_similar_jobs(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle finding similar jobs."""
        job_id = task.get("job_id")
        db = task.get("db")

        if not job_id:
            return {"status": "error", "message": "Missing required parameter: 'job_id' for similar_jobs task."}

        logger.info(f"Finding similar jobs for job_id {job_id}.")

        limit = task.get("limit", 5)
        matches = await self.matching_integrator.find_similar_jobs(
            job_id=job_id, db=db, limit=limit
        )
        return {
            "status": "completed",
            "job_id": job_id,
            "match_count": len(matches) if isinstance(matches, list) else 0,
            "results": matches,
        }
