"""
Applies all patches to the application.
Import this module in main.py before starting the application.

Note: Most patches have been consolidated into the EnhancedResumeParser.
"""
import logging

logger = logging.getLogger(__name__)

def apply_all_patches():
    """Apply all registered patches to the application."""
    logger.info("Applying application patches...")
    
    # No patches needed as functionality has been consolidated into EnhancedResumeParser
    logger.info("No patches to apply - using EnhancedResumeParser")
        
    # Apply description extractor fix to enhance experience and education details
    try:
        # This patch enhances descriptions in parsed resume data
        from backend.patches.description_extractor_fix import apply_description_extractor_fix
        apply_description_extractor_fix()
        logger.info("Successfully applied description extractor fix to enhance resume details")
    except Exception as e:
        logger.error(f"Failed to apply description extractor fix: {str(e)}")
        
    logger.info("All patches applied")
