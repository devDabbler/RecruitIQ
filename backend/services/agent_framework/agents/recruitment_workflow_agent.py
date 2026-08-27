from typing import Any, Dict, List
import logging
import uuid

from backend.services.agent_framework.base_agent import BaseAgent
from backend.services.agent_framework.agent_registry import agent_registry, register
from backend.services import service_registry

logger = logging.getLogger(__name__)

@register(
    name="RecruitmentWorkflowAgent",
    description="Orchestrates other agents to perform complex recruitment workflows."
)
class RecruitmentWorkflowAgent(BaseAgent):
    """Orchestrates other agents to perform complex recruitment workflows."""

    def __init__(self):
        # This agent orchestrates others, getting dependencies via the service registry
        # when it instantiates them.
        self.memory_manager = service_registry.provide_agent_memory_manager()

    async def execute(self, task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        workflow_name = task.get("workflow_name")
        if not workflow_name:
            return {"status": "error", "message": "'workflow_name' must be specified.", "session_id": str(uuid.uuid4())}

        session_id = str(uuid.uuid4())
        db_session = kwargs.get("db")
        logger.info(f"Executing recruitment workflow: {workflow_name} (Session: {session_id})")
        
        self.memory_manager.add_memory(
            db=db_session,
            session_id=session_id,
            agent_name=self.name,
            memory_type="observation",
            content={"event": "Workflow started", "workflow_name": workflow_name, "task": task}
        )

        try:
            if workflow_name == "full_source_to_hire":
                result = await self._workflow_full_source_to_hire(task, session_id=session_id, **kwargs)
            else:
                result = {"status": "error", "message": f"Unknown workflow: {workflow_name}"}
            
            self.memory_manager.add_memory(
                db=db_session,
                session_id=session_id,
                agent_name=self.name,
                memory_type="observation",
                content={"event": "Workflow finished", "workflow_name": workflow_name, "result": result}
            )
            return {"result": result, "session_id": session_id}
        except Exception as e:
            logger.exception(f"Error executing workflow '{workflow_name}': {e}")
            error_result = {"status": "error", "message": str(e)}
            self.memory_manager.add_memory(
                db=db_session,
                session_id=session_id,
                agent_name=self.name,
                memory_type="error",
                content={"event": "Workflow failed", "workflow_name": workflow_name, "error": str(e)}
            )
            return {"status": "error", "message": str(e), "session_id": session_id}

    def _get_agent(self, agent_name: str) -> BaseAgent:
        """Instantiates and returns an agent from the registry."""
        agent_class = agent_registry.get_agent_class(agent_name)
        
        # Simplified dependency injection.
        if agent_name == "ResumeProcessingAgent":
            return agent_class(resume_service=service_registry.provide_resume_service(), web_search_service=service_registry.provide_web_search_service())
        elif agent_name == "JobAnalysisAgent":
            return agent_class(job_service=service_registry.provide_job_service(), llm_service=service_registry.provide_llm_service())
        elif agent_name == "CandidateMatchingAgent":
            return agent_class(matching_integrator=service_registry.provide_matching_integrator(), llm_service=service_registry.provide_llm_service())
        elif agent_name == "CommunicationAgent":
            return agent_class(communications_service=service_registry.provide_communications_service(), llm_service=service_registry.provide_llm_service())
        elif agent_name == "MarketIntelAgent":
            return agent_class(web_search_service=service_registry.provide_web_search_service(), llm_service=service_registry.provide_llm_service(), job_service=service_registry.provide_job_service())
        else:
            return agent_class()

    async def _workflow_full_source_to_hire(self, task: Dict[str, Any], session_id: str, **kwargs) -> Dict[str, Any]:
        """Defines and executes the full source-to-hire workflow."""
        job_id = task.get("job_id")
        resume_files = task.get("resume_files")
        db_session = kwargs.get("db")

        if not all([job_id, resume_files, db_session]):
            return {"status": "error", "message": "'job_id', 'resume_files', and a db session are required."}

        workflow_steps = []
        results = {}

        # Fetch Job Title for later use
        job_service = service_registry.provide_job_service()
        job = job_service.get_job_by_id(db=db_session, job_id=job_id)
        if not job:
            return {"status": "error", "message": f"Job with ID {job_id} not found."}
        job_title = job.title
        results['job_title'] = job_title

        # Step 1: Process resumes
        logger.info("Workflow Step 1: Processing Resumes")
        resume_agent = self._get_agent("ResumeProcessingAgent")
        resume_result = await resume_agent.execute({"action": "process_resume_batch", "file_paths": resume_files}, db=db_session)
        workflow_steps.append({"step": "Resume Processing", "result": resume_result})
        self.memory_manager.add_memory(db_session, session_id, self.name, "action_result", {"step": "Resume Processing", "result": resume_result})
        if resume_result.get("status") != "completed":
            return {"status": "failed", "message": "Resume processing failed.", "steps": workflow_steps}
        results['processed_resumes'] = resume_result

        # Step 2: Match candidates
        logger.info("Workflow Step 2: Matching Candidates")
        candidate_ids = [r['candidate_id'] for r in resume_result.get('results', []) if 'candidate_id' in r]
        if not candidate_ids:
            return {"status": "failed", "message": "No candidates were processed from the provided resumes.", "steps": workflow_steps}
        
        matching_agent = self._get_agent("CandidateMatchingAgent")
        matching_result = await matching_agent.execute({"action": "find_optimal_matches", "job_id": job_id, "candidate_ids": candidate_ids}, db=db_session)
        workflow_steps.append({"step": "Candidate Matching", "result": matching_result})
        self.memory_manager.add_memory(db_session, session_id, self.name, "action_result", {"step": "Candidate Matching", "result": matching_result})
        if matching_result.get("status") != "completed":
            return {"status": "failed", "message": "Candidate matching failed.", "steps": workflow_steps}
        results['candidate_matches'] = matching_result

        # Step 3: Communicate with top candidates
        logger.info("Workflow Step 3: Communicating with Top Candidates")
        communication_agent = self._get_agent("CommunicationAgent")
        resume_service = service_registry.provide_resume_service()
        top_matches = matching_result.get("matches", [])[:3]
        
        communication_results = []
        for match in top_matches:
            candidate_id = match.get('candidate_id')
            candidate = resume_service.get_candidate_by_id(db=db_session, candidate_id=candidate_id)
            if not candidate:
                logger.warning(f"Could not find candidate with ID {candidate_id}. Skipping communication.")
                continue

            email_task = {
                "action": "send_email",
                "recipient": candidate.email,
                "subject": f"Invitation to Interview for {job_title}",
                "template": "initial_outreach",
                "context": {"candidate_name": candidate.name, "job_title": job_title}
            }
            email_result = await communication_agent.execute(email_task)
            communication_results.append({"step": f"Email to {candidate.name}", "result": email_result})
            self.memory_manager.add_memory(db_session, session_id, self.name, "action_result", {"step": f"Email to {candidate.name}", "result": email_result})

        workflow_steps.extend(communication_results)
        results['communications'] = communication_results

        return {"status": "completed", "workflow_name": "full_source_to_hire", "results": results, "steps": workflow_steps}
