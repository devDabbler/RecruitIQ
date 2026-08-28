# Central service registry for singleton/shared services
import logging
from .llm_service import LLMService, get_llm_service
from .web_search_service import WebSearchService, get_web_search_service
from .communications_service import CommunicationsService
from .matching_integrator import MatchingIntegrator
from .job_service import JobService
from ..utils.config import Settings
from .resume_service import ResumeService
from .storage_service import StorageService
from .crawler_service import CrawlerService
from .minio_storage_service import MinioStorageService
from .market_research_service import MarketResearchService

from .agent_framework.memory.agent_memory_manager import AgentMemoryManager

logger = logging.getLogger(__name__)

class ServiceRegistry:
    def __init__(self):
        self.settings = Settings()
        self._llm_service = None
        self._web_search_service = None
        self._communications_service = None
        self._matching_integrator = None
        self._job_service = None
        self._storage_service = None
        self._minio_storage_service = None

        self._resume_service = None
        self._crawler_service = None
        self._agent_memory_manager = None
        self._market_research_service = None

    @property
    def llm_service(self):
        if self._llm_service is None:
            self._llm_service = get_llm_service()
            # Don't preload embedding model during startup - load it when first accessed
        return self._llm_service

    @property
    def web_search_service(self):
        if self._web_search_service is None:
            self._web_search_service = get_web_search_service()
        return self._web_search_service

    @property
    def communications_service(self):
        if self._communications_service is None:
            self._communications_service = CommunicationsService(self.settings, self.llm_service)
        return self._communications_service

    @property
    def matching_integrator(self):
        if self._matching_integrator is None:
            self._matching_integrator = MatchingIntegrator(
                embedding_model=self.llm_service.get_embedding_model()
            )
        return self._matching_integrator

    @property
    def job_service(self):
        if self._job_service is None:
            self._job_service = JobService(self.llm_service)
        return self._job_service

    @property
    def storage_service(self):
        if self._storage_service is None:
            self._storage_service = StorageService()
        return self._storage_service

    @property
    def minio_storage_service(self):
        if self._minio_storage_service is None:
            self._minio_storage_service = MinioStorageService()
        return self._minio_storage_service

    @property
    def resume_service(self):
        if self._resume_service is None:
            # Try to use MinIO storage service, fallback to local storage if MinIO is not available
            try:
                storage_service = self.minio_storage_service
                # Test if MinIO is actually available by trying to initialize it
                if hasattr(storage_service, '_initialize_client'):
                    storage_service._initialize_client()
            except Exception as e:
                logger.warning(f"MinIO storage not available, falling back to local storage: {e}")
                storage_service = self.storage_service
            
            self._resume_service = ResumeService(
                storage_service=storage_service,
                llm_service=self.llm_service,
            )
        return self._resume_service

    @property
    def resume_parser(self):
        return self.resume_service

    @property
    def crawler_service(self):
        if self._crawler_service is None:
            self._crawler_service = CrawlerService(self.settings)
        return self._crawler_service

    @property
    def agent_memory_manager(self):
        if self._agent_memory_manager is None:
            self._agent_memory_manager = AgentMemoryManager(self.llm_service)
        return self._agent_memory_manager

    @property
    def market_research_service(self):
        if self._market_research_service is None:
            self._market_research_service = MarketResearchService(
                self.web_search_service, 
                self.llm_service
            )
        return self._market_research_service

_singleton_registry = None

def get_registry():
    global _singleton_registry
    if _singleton_registry is None:
        _singleton_registry = ServiceRegistry()
    return _singleton_registry

def get_service_registry():
    """Alias for get_registry() for backward compatibility."""
    return get_registry()

registry = get_registry()

def provide_llm_service():
    return registry.llm_service

def provide_web_search_service():
    return registry.web_search_service

def provide_job_service():
    return registry.job_service

def provide_resume_service():
    return registry.resume_service

def provide_storage_service():
    return registry.storage_service

def provide_minio_storage_service():
    return registry.minio_storage_service

def provide_resume_parser():
    return registry.resume_parser

def provide_crawler_service():
    return registry.crawler_service

def provide_communications_service():
    return registry.communications_service

def provide_matching_integrator():
    return registry.matching_integrator

def provide_agent_memory_manager():
    return registry.agent_memory_manager

def provide_market_research_service():
    return registry.market_research_service
