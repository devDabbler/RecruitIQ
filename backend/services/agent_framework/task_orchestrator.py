import inspect
import uuid
import asyncio
import logging
from typing import Any, Dict, Optional

from backend.services.service_registry import ServiceRegistry, get_registry
from .agent_registry import agent_registry
from .memory_manager import AgentMemoryManager

logger = logging.getLogger(__name__)

class TaskOrchestrator:
    """
    Coordinates agents to perform complex tasks, including running them asynchronously.
    """

    def __init__(self, service_registry: ServiceRegistry):
        self.registry = agent_registry
        self.memory = AgentMemoryManager()
        self.service_registry = service_registry
        self.tasks: Dict[str, Dict[str, Any]] = {}

    async def start_task(self, agent_name: str, task: Dict[str, Any]) -> str:
        """Starts a new task in the background and returns a task ID."""
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {"status": "processing", "result": None}
        asyncio.create_task(self._run_task_in_background(task_id, agent_name, task))
        return task_id

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the status and result of a task."""
        return self.tasks.get(task_id)

    async def _run_task_in_background(self, task_id: str, agent_name: str, task: Dict[str, Any]):
        """The actual task execution logic that runs in the background."""
        try:
            logger.info(f"Executing background task {task_id} for agent {agent_name}...")
            result = await self.execute_task(agent_name, task)
            self.tasks[task_id] = {"status": "completed", "result": result}
            logger.info(f"Task {task_id} completed successfully.")
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            self.tasks[task_id] = {"status": "failed", "error": str(e)}

    async def execute_task(self, agent_name: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a task using a single specified agent."""
        print("[Agent Debug] Available agents:", list(self.registry._agents.keys()))
        print("[Agent Debug] Requested agent:", agent_name)
        agent_class = self.registry.get_agent_class(agent_name)

        constructor_params = inspect.signature(agent_class.__init__).parameters
        dependencies = {}
        for param_name in constructor_params:
            if param_name == "self":
                continue
            if hasattr(self.service_registry, param_name):
                dependencies[param_name] = getattr(self.service_registry, param_name)
            else:
                logger.warning(f"Dependency '{param_name}' not found for agent '{agent_name}'.")

        agent_instance = agent_class(**dependencies)

        session_id = task.get("session_id")
        context = await self.memory.retrieve_context(session_id) if session_id else {}
        
        result = await agent_instance.execute(task, context=context)

        if session_id and result.get("updated_context"):
            await self.memory.store_context(session_id, result["updated_context"])

        return result

    async def execute_workflow(self, workflow_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a multi-agent workflow.
        This is a placeholder for a more complex workflow engine.
        """
        print(f"Executing workflow: {workflow_request}")
        # A real implementation would need a DSL or configuration for defining
        # workflows and would involve a sequence of calls to execute_task
        # with different agents, passing context between them.
        return {"status": "Workflow execution not yet implemented."}


# --- Singleton Orchestrator Instance ---
_orchestrator_instance: TaskOrchestrator | None = None


def get_agent_orchestrator() -> TaskOrchestrator:
    """
    Provides a singleton instance of the TaskOrchestrator.
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        service_registry = get_registry()
        _orchestrator_instance = TaskOrchestrator(service_registry)
    return _orchestrator_instance 