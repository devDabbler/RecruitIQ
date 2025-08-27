import json
from typing import Any, Dict, Optional

from backend.utils.redis_client import get_redis_client


class AgentMemoryManager:
    """
    Manages context and conversation memory for agents using Redis.
    """

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.prefix = "agent_memory:"

    async def _get_redis_client(self):
        if self.redis is None:
            self.redis = await get_redis_client()
        return self.redis

    async def store_context(self, session_id: str, context: Dict[str, Any]):
        """
        Stores conversation history and decisions for a session.
        """
        client = await self._get_redis_client()
        await client.set(f"{self.prefix}{session_id}", json.dumps(context))

    async def retrieve_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the context for a given session.
        """
        client = await self._get_redis_client()
        context_str = await client.get(f"{self.prefix}{session_id}")
        if context_str:
            return json.loads(context_str)
        return None

    async def learn_from_outcome(self, task_id: str, outcome: Dict[str, Any]):
        """
        Improves future decisions based on results.
        For now, this is a placeholder. In the future, this could be used
        to fine-tune models or adjust agent strategies.
        """
        # Placeholder for learning mechanism
        print(f"Learning from outcome of task {task_id}: {outcome}")
        client = await self._get_redis_client()
        await client.set(f"task_outcome:{task_id}", json.dumps(outcome)) 