from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.api.dependencies import get_db
from backend.services.agent_framework.agent_factory import AgentFactory
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/send_email", status_code=status.HTTP_200_OK)
async def send_email(request: dict, db: Session = Depends(get_db)):
    """Send an email to a candidate or client (Agentic Zero)"""
    try:
        agent = AgentFactory.create_agent("communication")
        task = {**request, "action": "send_email", "db": db}
        result = await agent.execute(task)
        return result
    except Exception as e:
        logger.exception(f"Agentic Zero error in send_email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    # LEGACY LOGIC: omitted for migration

@router.post("/schedule_interview", status_code=status.HTTP_200_OK)
async def schedule_interview(request: dict, db: Session = Depends(get_db)):
    """Schedule an interview with a candidate (Agentic Zero)"""
    try:
        agent = AgentFactory.create_agent("communication")
        task = {**request, "action": "schedule_interview", "db": db}
        result = await agent.execute(task)
        return result
    except Exception as e:
        logger.exception(f"Agentic Zero error in schedule_interview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    # LEGACY LOGIC: omitted for migration

# TODO: Add more communications endpoints as needed for future agentic actions
