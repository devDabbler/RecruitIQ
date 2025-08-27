from backend.services.market_intel_service import MarketIntelService
from backend.services.agent_framework.base_agent import BaseAgent

class MarketIntelAgent(BaseAgent):
    """Agentic zero implementation for market intelligence"""
    def __init__(self, market_intel_service: MarketIntelService = None, **kwargs):
        super().__init__(**kwargs)
        self.market_intel_service = market_intel_service or MarketIntelService()

    async def get_market_intel(self, query: str, **kwargs):
        base_results = await self.market_intel_service.get_market_intel(query)
        enhanced_results = self._enhance_market_data(base_results)
        return enhanced_results

    def _enhance_market_data(self, base_results):
        return base_results
