from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """
    Base class for all agents in the Agent Zero framework.
    Defines the common interface for agent functionality.
    """
    name: str
    description: str

    @abstractmethod
    async def execute(self, task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Executes a given task.

        Args:
            task: A dictionary containing task details.
            **kwargs: Dependencies and additional context for the agent.

        Returns:
            A dictionary containing the result of the task execution.
        """
        pass 