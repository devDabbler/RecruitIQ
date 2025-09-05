from backend.services.resume_service import ResumeService
from backend.services.agent_framework.base_agent import BaseAgent

class ResumeProcessingAgentLegacy(BaseAgent):
    """Legacy agent implementation for resume processing kept for backward compatibility.

    This legacy class is intentionally not registered with the agent registry to avoid
    name collisions with the newer agent implementation located in
    backend.services.agent_framework.agents.resume_processing_agent.
    """
    def __init__(self, resume_service: ResumeService = None, **kwargs):
        super().__init__(**kwargs)
        self.resume_service = resume_service or ResumeService()

    async def process_resume(self, file_path: str, **kwargs):
        # Agent preprocessing logic (legacy)
        base_results = await self.resume_service.parse_resume_file(file_path)
        enhanced_results = self._enhance_resume_data(base_results)
        return enhanced_results

    def _enhance_resume_data(self, base_results):
        # Legacy agent-specific enhancements (stub)
        return base_results
