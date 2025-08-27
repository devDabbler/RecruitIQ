"""
Local Model Service for interacting with locally-hosted models (Ollama).
This service provides methods to use locally trained models for various parsing tasks.
"""
import json
import logging
import os
import asyncio
import aiohttp
import re
from typing import Dict, List, Any, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)

class LocalModelService:
    """Service for interacting with locally-hosted models via Ollama API."""

    def __init__(self):
        """
        Initialize the local model service with warning messages about resume parsing.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.warning("LocalModelService is initialized but resume parsing functionality is disabled")
        self.logger.warning("Resume parsing should only use Nebius AI service (Phi-4)")
        
        # Set minimal properties
        self.host = None
        self.base_url = None
        self.api_endpoint = None
        self.session = None
        self.models = {
            "resume_parser": "[DISABLED]",
        }

    async def generate_text(self, prompt: str, model: str = None, temperature: float = 0.7, max_tokens: int = 1000):
        """
        Generate text using the local LLM model.
        
        Args:
            prompt: The prompt to send to the model
            model: The model to use (or default if None)
            temperature: Temperature for generation (0.0-1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dictionary with generated text
        """
        error_msg = "Ollama-based text generation is disabled. Use Nebius AI service instead."
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    def is_available(self):
        """
        Check if Ollama service is available.
        
        Returns:
            bool: True if Ollama is available, False otherwise
        """
        return False  # Always return False since we've disabled Ollama

    async def parse_resume_with_model(self, resume_text: str, model_name: str = None) -> Dict[str, Any]:
        """Parse a resume using the specified model or fallback to default model.
        
        Args:
            resume_text: The raw text of the resume to parse
            model_name: Optional name of the model to use
            
        Returns:
            Dict containing structured resume data
            
        Raises:
            RuntimeError: Always raises this error since Ollama-based resume parsing is disabled.
                       Resume parsing should only use Nebius AI service.
        """
        error_msg = "Ollama-based resume parsing is disabled. Resume parsing should only use Nebius AI service."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
        
        # NOTE: The code below is intentionally disabled (unreachable after raise statement)
        # It remains as reference only
        """
        # Log full prompt for debugging
        logger.info(f"Sending resume parsing prompt to local model. Prompt starts with: {prompt[:100]}...")
        
        # Try multiple models if needed
        best_result = None
        best_score = 0
        
        # Make sure we always try the llama3 model last, as it often gives the best results
        for model_name in [self.models["resume_parser"]]: # Only try available model
            try:
                logger.info(f"Attempting resume parsing with model: {model_name}")
                
                # Call local model with more explicit system message
                try:
                    logger.info(f"Attempting to generate response with model {model_name}")
                    response_text = await self._generate_response(
                        model_name, 
                        prompt, 
                        temperature=0.1,
                        max_tokens=4000
                    )
                    logger.info(f"Successfully received response from model {model_name}")
                except Exception as e:
                    logger.error(f"Failed to generate response with model {model_name}: {str(e)}")
                    # Try with a fallback model if available
                    fallback_models = ["llama3", "llama3:latest", "gemma:2b"]
                    
                    for fallback in fallback_models:
                        try:
                            logger.warning(f"Attempting fallback with model {fallback}")
                            response_text = await self._generate_response(
                                fallback,
                                prompt,
                                temperature=0.1,
                                max_tokens=4000
                            )
                            logger.info(f"Successfully received response from fallback model {fallback}")
                            model_name = fallback
                            break
                        except Exception as fallback_e:
                            logger.error(f"Fallback model {fallback} also failed: {str(fallback_e)}")
                            response_text = ""
                            continue
                
                # Rest of the function...
            except Exception as e:
                logger.warning(f"Error with model {model_name}: {str(e)}")
                continue
        
        # If we get here, all models failed
        logger.error("All local models failed to parse resume")
        return {}
        """

    async def parse_resume(self, resume_text: str) -> Dict[str, Any]:
        """
        Parse a resume using the default model.
        
        Args:
            resume_text: The raw text of the resume to parse
            
        Returns:
            Dict containing structured resume data
            
        Raises:
            RuntimeError: Always raises this error since Ollama-based resume parsing is disabled.
                       Resume parsing should only use Nebius AI service.
        """
        error_msg = "Ollama-based resume parsing is disabled. Resume parsing should only use Nebius AI service."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    async def parse_job_description(self, job_text: str) -> Dict[str, Any]:
        """Parse a job description using the configured job parser model.
        
        Args:
            job_text: The raw text of the job description to parse
            
        Returns:
            Dict containing structured job data
        """
        error_msg = "Ollama-based job parsing is disabled. Use Nebius AI service instead."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    async def _generate_response(
        self, 
        model_name: str, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 2048
    ):
        """
        Generate a response from a local Ollama model, handling streaming output by concatenating all 'response' fields.
        
        Args:
            model_name: Name of the Ollama model to use
            prompt: The prompt to send to the model
            temperature: Temperature setting (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
        Returns:
            String response from the model (assembled from all streamed 'response' fields)
        """
        error_msg = "Ollama API calls are disabled. Use Nebius AI service instead."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    def _extract_json_from_response(self, response_text: str):
        """
        Extract JSON from model response text.
        
        Args:
            response_text: Text response from the model
            
        Returns:
            Dict extracted from JSON in response
        """
        error_msg = "Ollama response processing is disabled. Use Nebius AI service instead."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    async def generate_response(self, model_name, system_prompt, user_prompt, temperature=0.7, max_tokens=2000, timeout=30):
        """
        Generate a response from the model using system and user prompts.
        
        Args:
            model_name: Name of the model to use
            system_prompt: System context/instructions
            user_prompt: User query/input
            temperature: Model temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            timeout: Timeout in seconds
            
        Returns:
            Generated response as a dictionary
        """
        error_msg = "Ollama-based response generation is disabled. Use Nebius AI service instead."
        logger.error(error_msg)
        raise RuntimeError(error_msg)


# Singleton pattern for service access
_local_model_service = None

def get_local_model_service():
    """
    Get a singleton instance of the LocalModelService.
    
    Returns:
        LocalModelService instance
    """
    global _local_model_service
    if _local_model_service is None:
        _local_model_service = LocalModelService()
    return _local_model_service
