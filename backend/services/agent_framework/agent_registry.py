from typing import Dict, Type
from .base_agent import BaseAgent


class AgentRegistry:
    """
    A registry for discovering and managing agent classes.
    """

    def __init__(self):
        self._agents: Dict[str, Type[BaseAgent]] = {}

    def register(self, agent_class: Type[BaseAgent]):
        """
        Registers an agent class.
        """
        agent_name = getattr(agent_class, "name", agent_class.__name__)
        if agent_name in self._agents:
            # Check if it's the same class being registered again
            existing = self._agents[agent_name]
            if existing == agent_class:
                # Same class object, ignore duplicate
                return
            # If classes are different objects but come from the same source file
            # it is likely an import aliasing issue (module imported under two names).
            try:
                import inspect
                existing_file = inspect.getsourcefile(existing) or inspect.getfile(existing)
                new_file = inspect.getsourcefile(agent_class) or inspect.getfile(agent_class)
                if existing_file == new_file:
                    # Same origin file; treat as duplicate registration and ignore
                    return
            except Exception:
                # If we can't determine file origin, fall through to error
                pass
            # Different class with same name from different source: raise error
            raise ValueError(f"Agent with name '{agent_name}' is already registered with a different class.")
        self._agents[agent_name] = agent_class
        print(f"Agent '{agent_name}' registered.")

    def get_agent_class(self, name: str) -> Type[BaseAgent]:
        """
        Retrieves an agent class by its name.
        """
        agent_class = self._agents.get(name)
        if not agent_class:
            raise ValueError(f"No agent found with name '{name}'.")
        return agent_class

    def list_agents(self) -> Dict[str, str]:
        """
        Lists all registered agents and their descriptions.
        """
        return {
            name: getattr(cls, "description", "No description provided.")
            for name, cls in self._agents.items()
        }


# Global registry instance
agent_registry = AgentRegistry()


def register(name: str, description: str):
    """
    A decorator to register agent classes with the global registry.
    """

    def decorator(agent_class: Type[BaseAgent]) -> Type[BaseAgent]:
        agent_class.name = name
        agent_class.description = description
        agent_registry.register(agent_class)
        return agent_class

    return decorator 