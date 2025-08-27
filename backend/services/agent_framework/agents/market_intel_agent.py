from typing import Any, Dict, List
import logging

from backend.services.agent_framework.base_agent import BaseAgent
from backend.services.agent_framework.agent_registry import register
from backend.services.web_search_service import WebSearchService
from backend.services.llm_service import LLMService
from backend.services.job_service import JobService
from backend.services.market_research_service import MarketResearchService

logger = logging.getLogger(__name__)

@register(
    name="MarketIntelAgent",
    description="Provides market intelligence on talent pools, salaries, and competitor hiring."
)
class MarketIntelAgent(BaseAgent):
    """Provides market intelligence by analyzing external and internal data."""

    def __init__(self, web_search_service: WebSearchService, llm_service: LLMService, job_service: JobService):
        self.web_search_service = web_search_service
        self.llm_service = llm_service
        self.job_service = job_service
        self.market_research_service = MarketResearchService(web_search_service, llm_service)

    async def execute(self, task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        action = task.get("action")
        if not action:
            return {"status": "error", "message": "'action' must be specified."}

        logger.info(f"MarketIntelAgent executing action: {action}")

        try:
            if action == "analyze_talent_pool":
                return await self._analyze_talent_pool(task)
            elif action == "benchmark_salary":
                return await self._benchmark_salary(task)
            elif action == "track_competitor_hiring":
                return await self._track_competitor_hiring(task)
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            logger.exception(f"Error executing market intel action '{action}': {e}")
            return {"status": "error", "message": str(e)}

    async def _analyze_talent_pool(self, task: Dict[str, Any]) -> Dict[str, Any]:
        role_description = task.get("role_description")
        location = task.get("location")
        if not role_description or not location:
            return {"status": "error", "message": "'role_description' and 'location' are required."}

        query = f"talent pool analysis for {role_description} in {location}"
        search_results = await self.web_search_service.search(query)

        prompt = f"""
        Based on the following search results, analyze the talent pool for '{role_description}' in '{location}'.
        Provide an overview of talent availability, key skills in demand, and top companies hiring for this role.
        
        Search Results:
        {search_results}
        
        Analysis:
        """
        analysis = await self.llm_service.generate_text_async(prompt, max_tokens=1000, task_type="market_research")
        return {"status": "completed", "analysis": analysis.content if hasattr(analysis, 'content') else str(analysis)}

    async def _benchmark_salary(self, task: Dict[str, Any]) -> Dict[str, Any]:
        job_title = task.get("job_title")
        location = task.get("location")
        experience_level = task.get("experience_level")  # Optional: entry, mid, senior, lead
        
        if not job_title or not location:
            return {"status": "error", "message": "'job_title' and 'location' are required."}

        try:
            # Use the enhanced market research service
            result = await self.market_research_service.get_comprehensive_salary_benchmark(
                job_title=job_title,
                location=location,
                experience_level=experience_level
            )
            
            if result["status"] == "success":
                return {"status": "completed", "benchmark": result["data"]}
            else:
                return {"status": "error", "message": result.get("message", "Unknown error")}
                
        except Exception as e:
            logger.error(f"Error in enhanced salary benchmark: {e}")
            return {"status": "error", "message": f"Failed to generate salary benchmark: {str(e)}"}

    async def _track_competitor_hiring(self, task: Dict[str, Any]) -> Dict[str, Any]:
        competitors = task.get("competitors")
        role = task.get("role")
        if not competitors or not role:
            return {"status": "error", "message": "'competitors' and 'role' are required."}

        all_results = []
        for competitor in competitors:
            query = f'{competitor} hiring for "{role}" roles'
            results = await self.web_search_service.search(query)
            all_results.append({competitor: results})

        prompt = f"""
        Analyze the hiring trends of the following competitors for '{role}' roles based on the search results.
        Summarize the hiring activity for each competitor and identify any overall market trends.
        
        Hiring Data:
        {all_results}
        
        Competitor Hiring Analysis:
        """
        analysis = await self.llm_service.generate_text_async(prompt, max_tokens=1200, task_type="market_research")
        return {"status": "completed", "analysis": analysis.content if hasattr(analysis, 'content') else str(analysis)}
