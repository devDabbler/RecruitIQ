from backend.services.communications_service import CommunicationsService
from backend.services.agent_framework.base_agent import BaseAgent

class CommunicationAgent(BaseAgent):
    """Agentic zero implementation for communications"""
    def __init__(self, communications_service: CommunicationsService = None, **kwargs):
        super().__init__(**kwargs)
        self.communications_service = communications_service or CommunicationsService()

    async def handle_communication(self, message: str, **kwargs):
        base_results = await self.communications_service.handle_communication(message)
        enhanced_results = self._enhance_communication_data(base_results)
        return enhanced_results

    def _enhance_communication_data(self, base_results):
        return base_results
