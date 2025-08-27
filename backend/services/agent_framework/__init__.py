"""
Agent Framework for RecruitIQ
This module provides a centralized way to initialize and manage all agents.
"""

import importlib
import logging
from typing import Dict, Type
from .agent_registry import agent_registry, register
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Track if agents have been initialized
_agents_initialized = False

def initialize_agents():
    """
    Initialize all agents and register them with the agent registry.
    This function ensures agents are loaded only once.
    """
    global _agents_initialized
    
    if _agents_initialized:
        logger.debug("Agents already initialized, skipping...")
        return
    
    logger.info("Initializing agent framework...")
    
    # Import all agent modules to trigger registration
    agent_modules = [
        "resume_processing_agent",
        "candidate_matching_agent", 
        "job_analysis_agent",
        "communication_agent",
        "market_intel_agent",
        "travel_assistant_agent",
        "recruitment_workflow_agent"
    ]
    
    for module_name in agent_modules:
        try:
            importlib.import_module(f".agents.{module_name}", package=__name__)
            logger.debug(f"Loaded agent module: {module_name}")
        except ImportError as e:
            logger.warning(f"Failed to load agent module {module_name}: {e}")
        except Exception as e:
            logger.error(f"Error loading agent module {module_name}: {e}")
    
    _agents_initialized = True
    logger.info(f"Agent framework initialized with {len(agent_registry._agents)} agents")

def get_agent_class(agent_name: str) -> Type[BaseAgent]:
    """
    Get an agent class by name.
    """
    if not _agents_initialized:
        initialize_agents()
    
    return agent_registry.get_agent_class(agent_name)

def list_agents() -> Dict[str, str]:
    """
    List all registered agents and their descriptions.
    """
    if not _agents_initialized:
        initialize_agents()
    
    return agent_registry.list_agents()

# DO NOT initialize agents when this module is imported - this causes circular imports
# Instead, initialize agents only when explicitly requested
# initialize_agents()