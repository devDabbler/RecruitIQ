from typing import Dict, Any, Type

from backend.services.agent_framework.base_agent import BaseAgent
# Import actual agent implementations from agents subdirectory
from backend.services.agent_framework.agents.resume_processing_agent import ResumeProcessingAgent
from backend.services.agent_framework.agents.candidate_matching_agent import CandidateMatchingAgent
from backend.services.agent_framework.agents.job_analysis_agent import JobAnalysisAgent
from backend.services.agent_framework.agents.communication_agent import CommunicationAgent
from backend.services.agent_framework.agents.market_intel_agent import MarketIntelAgent

# Import service registry for proper dependency injection
from backend.services.service_registry import ServiceRegistry

class AgentFactory:
    """Factory for creating and managing agentic zero agents"""
    _agents: Dict[str, Type[BaseAgent]] = {
        "resume": ResumeProcessingAgent,
        "matching": CandidateMatchingAgent,
        "job": JobAnalysisAgent,
        "communication": CommunicationAgent,
        "intelligence": MarketIntelAgent
    }
    
    # Singleton service registry instance
    _service_registry = None

    @classmethod
    def _get_service_registry(cls):
        """Get singleton service registry instance"""
        if cls._service_registry is None:
            cls._service_registry = ServiceRegistry()
        return cls._service_registry

    @classmethod
    def create_agent(cls, agent_type: str, **kwargs) -> BaseAgent:
        """Create an agent instance of the specified type with proper dependency injection"""
        if agent_type not in cls._agents:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        # Get the service registry
        registry = cls._get_service_registry()
        
        # Initialize required services based on agent type
        if agent_type == "matching":
            # CandidateMatchingAgent needs MatchingIntegrator
            return cls._agents[agent_type](matching_integrator=registry.matching_integrator)
        
        elif agent_type == "job":
            # JobAnalysisAgent needs JobService and LLMService
            return cls._agents[agent_type](
                job_service=registry.job_service,
                llm_service=registry.llm_service
            )
        
        elif agent_type == "resume":
            # ResumeProcessingAgent needs multiple services
            return cls._agents[agent_type](
                resume_service=registry.resume_service,
                storage_service=registry.storage_service,
                llm_service=registry.llm_service,
                web_search_service=registry.web_search_service,
                job_service=registry.job_service
            )
        
        elif agent_type == "intelligence":
            # MarketIntelAgent needs WebSearchService, LLMService, and JobService
            return cls._agents[agent_type](
                web_search_service=registry.web_search_service,
                llm_service=registry.llm_service,
                job_service=registry.job_service
            )
        
        elif agent_type == "communication":
            # CommunicationAgent needs CommunicationsService and LLMService
            return cls._agents[agent_type](
                communications_service=registry.communications_service,
                llm_service=registry.llm_service
            )
        
        else:
            # For other agents, try to initialize with provided kwargs
            return cls._agents[agent_type](**kwargs)
