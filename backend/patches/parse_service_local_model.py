"""
Patch to integrate local model parsing into the existing parse_service.py.
This adds a local-first strategy with fallback to API-based models.
"""
import logging
from typing import Dict, List, Any, Optional

from backend.services.parse_service import ParseService
from backend.services.local_model_service import get_local_model_service

logger = logging.getLogger(__name__)

# Patch the _extract_structured_data method to try local model first
async def _extract_structured_data_with_local_model(self, sections: List) -> Dict:
    """Extract structured data from sections using local model with LLM fallback."""
    try:
        # Combine section content for processing
        section_text = "\n\n".join([
            f"## {section.title}\n{section.content}" 
            for section in sections if section.title and section.content
        ])
        
        # Try using the local model first
        local_model_service = get_local_model_service()
        local_model_available = await local_model_service.is_available()
        
        if local_model_available:
            # --- Step 1: Try local model first ---
            logger.info("Attempting to extract structured data using local model...")
            local_model_data = await local_model_service.parse_resume(section_text)
            
            # Check if we got valid results from local model
            if (local_model_data and 
                "personal_info" in local_model_data and 
                local_model_data["personal_info"]):
                logger.info("Successfully extracted data with local model")
                
                # Ensure the structure is correct
                if "skills" not in local_model_data:
                    local_model_data["skills"] = []
                if "education" not in local_model_data:
                    local_model_data["education"] = []
                if "experience" not in local_model_data:
                    local_model_data["experience"] = []
                
                return local_model_data
            else:
                logger.warning("Local model extraction returned invalid or incomplete data")
        else:
            logger.info("Local model not available, proceeding with LLM services")
        
        # --- Fall back to the original implementation ---
        # Get the original method bound to self
        original_method = self.__class__._extract_structured_data.__get__(self, self.__class__)
        
        # Call the original method
        return await original_method(sections)
        
    except Exception as e:
        logger.error(f"Error in patched _extract_structured_data: {str(e)}")
        # Fall back to the original method
        original_method = self.__class__._extract_structured_data.__get__(self, self.__class__)
        return await original_method(sections)

def apply_patch():
    """Apply the local model patch to ParseService."""
    # Save the original method
    ParseService._original_extract_structured_data = ParseService._extract_structured_data
    
    # Replace with patched method
    ParseService._extract_structured_data = _extract_structured_data_with_local_model
    
    logger.info("Applied local model patch to ParseService")
