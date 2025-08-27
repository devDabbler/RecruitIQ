from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.api.dependencies import get_db
from backend.services.agent_framework.agent_factory import AgentFactory
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/plan_interview_travel", status_code=status.HTTP_200_OK)
async def plan_interview_travel(request: dict, db: Session = Depends(get_db)):
    """Plan travel for a candidate interview (Agentic Zero)"""
    try:
        agent = AgentFactory.create_agent("travel")
        task = {**request, "action": "plan_interview_travel", "db": db}
        result = await agent.execute(task)
        return result
    except Exception as e:
        logger.exception(f"Agentic Zero error in plan_interview_travel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    # LEGACY LOGIC: omitted for migration

# TODO: Add more travel endpoints as needed for future agentic actions
