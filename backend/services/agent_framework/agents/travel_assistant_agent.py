from typing import Any, Dict, Optional
import logging
import json

from backend.services.agent_framework.base_agent import BaseAgent
from backend.services.agent_framework.agent_registry import register
from backend.services.recruitiq_travel_service import RecruitIQTravelService
from backend.services.llm_service import LLMService

logger = logging.getLogger(__name__)

@register(
    name="TravelAssistantAgent",
    description="Assists with planning and providing information for candidate travel."
)
class TravelAssistantAgent(BaseAgent):
    """Handles travel-related tasks for candidates, like planning interview travel."""

    def __init__(self, travel_service: RecruitIQTravelService, llm_service: LLMService):
        self.travel_service = travel_service
        self.llm_service = llm_service

    async def execute(self, task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        action = task.get("action")
        if not action:
            return {"status": "error", "message": "'action' must be specified."}

        logger.info(f"TravelAssistantAgent executing action: {action}")

        try:
            if action == "plan_interview_travel":
                return await self._plan_interview_travel(task)
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            logger.exception(f"Error executing travel assistant action '{action}': {e}")
            return {"status": "error", "message": str(e)}

    async def _plan_interview_travel(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Plans travel for a candidate's interview."""
        query = task.get("query")
        origin = task.get("origin")
        destination = task.get("destination")
        travel_date = task.get("travel_date")

        if not query and not (origin and destination):
            return {"status": "error", "message": "Either 'query' or both 'origin' and 'destination' must be provided."}

        # If we only have a query, use LLM to extract entities
        if query and not (origin and destination):
            extracted_entities = await self._extract_travel_entities(query)
            origin = extracted_entities.get("origin")
            destination = extracted_entities.get("destination")
            if not origin or not destination:
                return {"status": "error", "message": f"Could not extract origin and destination from query: '{query}'"}

        # Classify intent
        intent_result = self.travel_service.classify_recruiting_intent(query or f"travel from {origin} to {destination}")
        intent_type = intent_result.get("intent_type", "interview_travel")

        logger.info(f"Planning travel from {origin} to {destination} for intent '{intent_type}'.")

        # Gather travel data
        travel_plan = await self.travel_service.gather_recruiting_travel_data(
            origin=origin,
            destination=destination,
            intent_type=intent_type,
            travel_date=travel_date
        )

        return {"status": "completed", "plan": travel_plan}

    async def _extract_travel_entities(self, query: str) -> Dict[str, Optional[str]]:
        """Use LLM to extract travel entities from a natural language query."""
        prompt = f"""
        Extract the origin and destination from the following travel query. Respond in JSON format with keys "origin" and "destination".
        Query: "{query}"
        JSON:
        """
        
        response = await self.llm_service.generate_text_async(prompt, max_tokens=100)
        response_text = response.content if hasattr(response, 'content') else str(response)

        try:
            entities = json.loads(response_text)
            return {
                "origin": entities.get("origin"),
                "destination": entities.get("destination")
            }
        except json.JSONDecodeError:
            logger.error(f"Failed to decode LLM response for travel entity extraction: {response_text}")
            return {"origin": None, "destination": None}
