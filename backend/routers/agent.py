# backend/routers/agent.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from backend.services.agent_framework.agent_registry import AgentRegistry
from backend.services.service_registry import provide_agent_memory_manager
from backend.utils.database import get_db

router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
)

@router.post("/invoke")
async def invoke_agent(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Invokes a registered agent to perform a task.
    The payload should specify the agent_name and the task details.
    """
    agent_name = payload.get("agent_name")
    task = payload.get("task")

    if not agent_name or not task:
        raise HTTPException(status_code=400, detail="'agent_name' and 'task' must be provided.")

    try:
        agent_class = AgentRegistry.get_agent(agent_name)
        if not agent_class:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

        agent_instance = agent_class()
        # The execute method should return a dict, we'll add the session_id to it
        result = await agent_instance.execute(task, db=db)
        
        # The session_id is generated within the agent's execute method
        # We need to retrieve it to allow the frontend to query for memories.
        # This assumes the agent's result dictionary contains the session_id.
        if isinstance(result, dict) and "session_id" in result:
            return result
        else:
            # This case handles agents that might not be returning the session_id.
            # For now, we'll just return the result as is.
            return {"result": result, "session_id": None}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/memories")
def get_session_memories(session_id: str, db: Session = Depends(get_db)):
    """Retrieves all memories for a given session ID."""
    try:
        memory_manager = provide_agent_memory_manager()
        memories = memory_manager.get_memories_by_session(db, session_id)
        return [memory.__dict__ for memory in memories] # Return as serializable list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
