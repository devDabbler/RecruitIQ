from backend.services.travel_service import TravelService
from backend.services.agent_framework.base_agent import BaseAgent

class TravelAssistantAgent(BaseAgent):
    """Agentic zero implementation for travel assistance"""
    def __init__(self, travel_service: TravelService = None, **kwargs):
        super().__init__(**kwargs)
        self.travel_service = travel_service or TravelService()

    async def assist_travel(self, itinerary: dict, **kwargs):
        base_results = await self.travel_service.assist_travel(itinerary)
        enhanced_results = self._enhance_travel_data(base_results)
        return enhanced_results

    def _enhance_travel_data(self, base_results):
        return base_results
