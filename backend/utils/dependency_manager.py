# backend/utils/dependency_manager.py
"""
Centralized dependency manager for shared resources (spaCy models, LLMService, StorageService, etc).
"""
import spacy
import logging
from backend.services.llm_service import LLMService
from backend.services.storage_service import StorageService
from backend.utils.config import Settings

logger = logging.getLogger(__name__)

class DependencyManager:
    def __init__(self):
        self._spacy_model = None
        self._llm_service = None
        self._storage_service = None
        self._settings = Settings()

    def get_spacy_model(self, model_name="en_core_web_lg"):
        """
        Get or load the spaCy model.
        
        Args:
            model_name (str): Name of the spaCy model to load. Defaults to 'en_core_web_lg'.
            
        Returns:
            spacy.Language: Loaded spaCy model.
        """
        if not self._spacy_model:
            try:
                self._spacy_model = spacy.load(model_name)
                logger.info(f"Loaded spaCy model: {model_name}")
            except OSError:
                logger.warning(f"spaCy model '{model_name}' not found. Falling back to 'en_core_web_lg'")
                try:
                    self._spacy_model = spacy.load("en_core_web_lg")
                    logger.info("Loaded fallback spaCy model: en_core_web_lg")
                except OSError:
                    logger.error("Failed to load any spaCy model. Please run the download_spacy_model.py script.")
                    raise
        return self._spacy_model

    def get_llm_service(self):
        if not self._llm_service:
            self._llm_service = LLMService(self._settings)
        return self._llm_service

    def get_storage_service(self):
        if not self._storage_service:
            self._storage_service = StorageService()
        return self._storage_service

# Singleton instance
dependency_manager = DependencyManager()
