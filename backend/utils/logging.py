import logging
from typing import Dict, Any

# Set up logger
logger = logging.getLogger("resume_parsing")


def log_parsing_errors(error: Exception, resume_text: str, metadata: Dict[str, Any] = None):
    """Log parsing errors with context."""
    error_info = {
        "error": str(error),
        "resume_preview": resume_text[:200] if resume_text else "",
        "metadata": metadata or {}
    }
    logger.error(f"Resume parsing failed: {error_info}")


def setup_logging():
    """Set up logging configuration for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('resume_parsing.log')
        ]
    )
