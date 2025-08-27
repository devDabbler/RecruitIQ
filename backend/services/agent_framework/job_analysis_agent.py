from backend.services.job_service import JobService
from backend.services.agent_framework.base_agent import BaseAgent

class JobAnalysisAgent(BaseAgent):
    """Agentic zero implementation for job analysis"""
    def __init__(self, job_service: JobService = None, **kwargs):
        super().__init__(**kwargs)
        self.job_service = job_service or JobService()

    async def analyze_job(self, job_id: str, **kwargs):
        base_results = await self.job_service.analyze_job(job_id)
        enhanced_results = self._enhance_job_data(base_results)
        return enhanced_results

    def _enhance_job_data(self, base_results):
        return base_results
