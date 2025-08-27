import logging
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.models.models import AgentMemory

logger = logging.getLogger(__name__)

class AgentMemoryManager:
    """Manages the short-term and long-term memory for agents."""

    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.embedding_model = self.llm_service.get_embedding_model()

    def add_memory(
        self,
        db: Session,
        session_id: str,
        agent_name: str,
        memory_type: str,
        content: Dict[str, Any],
        importance: float = 0.5,
    ):
        """Adds a new memory to the database, including its vector embedding."""
        try:
            # Generate embedding from memory content
            content_str = json.dumps(content)
            embedding = self.embedding_model.embed_query(content_str)

            memory = AgentMemory(
                session_id=session_id,
                agent_name=agent_name,
                memory_type=memory_type,
                content=content,
                importance=importance,
                embedding=embedding,  # Add the embedding
            )
            db.add(memory)
            db.commit()
            logger.info(f"Added memory with embedding for agent '{agent_name}'.")
            return memory
        except Exception as e:
            db.rollback()
            logger.exception(f"Failed to add memory for agent '{agent_name}': {e}")
            return None

    def get_memories(
        self,
        db: Session,
        session_id: str,
        agent_name: str,
        limit: int = 100,
    ) -> List[AgentMemory]:
        """Retrieves recent memories for a given agent and session."""
        try:
            memories = (
                db.query(AgentMemory)
                .filter(AgentMemory.session_id == session_id, AgentMemory.agent_name == agent_name)
                .order_by(AgentMemory.created_at.desc())
                .limit(limit)
                .all()
            )
            return memories
        except Exception as e:
            logger.exception(f"Failed to retrieve memories for agent '{agent_name}': {e}")
            return []

    def get_memories_by_session(self, db: Session, session_id: str, limit: int = 100) -> List[AgentMemory]:
        """Retrieves all memories for a given session, ordered by creation time."""
        try:
            return (
                db.query(AgentMemory)
                .filter(AgentMemory.session_id == session_id)
                .order_by(AgentMemory.created_at.asc())
                .limit(limit)
                .all()
            )
        except Exception as e:
            logger.exception(f"Failed to retrieve memories for session '{session_id}': {e}")
            return []

    def get_relevant_memories(
        self,
        db: Session,
        session_id: str,
        agent_name: str,
        query_embedding: List[float],
        limit: int = 10,
    ) -> List[AgentMemory]:
        """
        Retrieves memories most relevant to a given query embedding using vector similarity search.
        """
        try:
            # Using l2_distance for similarity search. The lower the distance, the more similar.
            relevant_memories = (
                db.query(AgentMemory)
                .filter(
                    AgentMemory.session_id == session_id,
                    AgentMemory.agent_name == agent_name
                )
                .order_by(AgentMemory.embedding.l2_distance(query_embedding))
                .limit(limit)
                .all()
            )
            return relevant_memories
        except Exception as e:
            logger.exception(f"Failed to retrieve relevant memories for agent '{agent_name}': {e}")
            return []

    def clear_session_memories(self, db: Session, session_id: str):
        """Deletes all memories associated with a specific session."""
        try:
            db.query(AgentMemory).filter(AgentMemory.session_id == session_id).delete()
            db.commit()
            logger.info(f"Cleared all memories for session '{session_id}'.")
        except Exception as e:
            db.rollback()
            logger.exception(f"Failed to clear memories for session '{session_id}': {e}")
