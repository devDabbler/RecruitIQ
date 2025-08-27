"""
Factory for ResumeParser
Decoupled from parser.py to avoid circular imports.
"""
from typing import Any, Optional
from .resume_parser_main import ResumeParser

def create_resume_parser(storage_service: Any, llm_service: Any, config_path: Optional[str] = None) -> ResumeParser:
    """
    Factory function to create a configured ResumeParser instance
    Args:
        storage_service: Service for handling file storage
        llm_service: Service for LLM operations
        config_path: Optional path to configuration file
    Returns:
        Initialized ResumeParser
    """
    return ResumeParser(storage_service, llm_service, config_path)
