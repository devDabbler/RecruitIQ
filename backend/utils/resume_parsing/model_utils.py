"""
Utility functions for working with fine-tuned models in the resume parser.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Define paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
FINE_TUNED_MODELS_DIR = BASE_DIR / "training_data" / "fine_tuned_models"

def get_model_path(model_name: str) -> str:
    """
    Get path to fine-tuned model if available, otherwise use base model.
    
    Args:
        model_name: Base model name (e.g., "tinyllama", "phi", "mistral")
        
    Returns:
        str: Model name to use (either fine-tuned model name or base model name)
    """
    # Extract base model name (remove version tag if present)
    base_model = model_name.split(':')[0]
    
    # Check if fine-tuned model exists
    fine_tuned_path = FINE_TUNED_MODELS_DIR / base_model
    fine_tuned_model = f"resume-parser-{base_model}"
    
    # Check if the fine-tuned model exists in Ollama
    try:
        import httpx
        import asyncio
        
        async def check_model_exists():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get("http://localhost:11434/api/tags")
                    if response.status_code == 200:
                        models = response.json().get("models", [])
                        model_names = [model["name"] for model in models]
                        return fine_tuned_model in model_names
                    return False
            except Exception as e:
                logger.error(f"Error checking for fine-tuned model: {e}")
                return False
        
        # Run the async function
        model_exists = asyncio.run(check_model_exists())
        
        if model_exists:
            logger.info(f"Using fine-tuned model: {fine_tuned_model}")
            return fine_tuned_model
    except Exception as e:
        logger.error(f"Error checking for fine-tuned model: {e}")
    
    # Fall back to base model
    logger.info(f"Fine-tuned model not found, using base model: {model_name}")
    return model_name

def get_model_metadata(model_name: str) -> Dict[str, Any]:
    """
    Get metadata for a fine-tuned model.
    
    Args:
        model_name: Base model name (e.g., "tinyllama", "phi", "mistral")
        
    Returns:
        Dict[str, Any]: Model metadata or empty dict if not found
    """
    # Extract base model name (remove version tag if present)
    base_model = model_name.split(':')[0]
    
    # Check if fine-tuned model exists
    metadata_path = FINE_TUNED_MODELS_DIR / base_model / "metadata.json"
    
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading model metadata: {e}")
    
    return {}
