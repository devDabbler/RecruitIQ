"""
Nebius AI Service for handling interactions with Nebius AI API.
This service provides LLM capabilities for resume parsing and other AI tasks.
"""
import json
import logging
import os
import time
import random
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple

import httpx
import asyncio
import re

# Remove agent framework dependency to break circular import
# from backend.services.agent_framework.exceptions import ParsingError
# Using standard Exception instead
from backend.utils.config import Settings

class ParsingError(Exception):
    """Custom exception for parsing errors."""
    pass

logger = logging.getLogger(__name__)

from backend.utils.resume_parsing.models.resume_schema import ResumeData

class NebiusAIService:
    """
    Service for handling interactions with Nebius AI API for LLM models.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Nebius AI service with configuration.
        
        Args:
            config: Configuration dictionary containing API settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.base_url = config.get("nebius_base_url", "https://api.studio.nebius.com/v1/")
        self.model = config.get("model", "microsoft/phi-4")
        self.api_key = config.get("api_key", "")
        self.timeout = config.get("timeout", 30.0)
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 500)
        
        self.logger.info(f"Initialized Nebius AI service with model: {self.model}")
        
    async def _retry_with_backoff(self, callback, max_retries: int = 3, initial_backoff: float = 2.0) -> Tuple[bool, Any, Optional[Exception]]:
        """
        Execute a callback with exponential backoff retry logic
        
        Args:
            callback: Async function to execute
            max_retries: Maximum number of retries before giving up
            initial_backoff: Initial backoff time in seconds
            
        Returns:
            Tuple of (success, result, exception)
        """
        attempt = 0
        last_exception = None
        
        while attempt <= max_retries:
            try:
                if attempt > 0:
                    backoff = initial_backoff * (2 ** (attempt - 1))
                    jitter = random.uniform(0, 0.1 * backoff)
                    wait_time = backoff + jitter
                    self.logger.info(f"Retry attempt {attempt}/{max_retries} after {wait_time:.2f}s backoff")
                    await asyncio.sleep(wait_time)
                
                result = await callback()
                return True, result, None
                
            except Exception as e:
                last_exception = e
                self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                attempt += 1
        
        return False, None, last_exception
    
    async def generate_completion(self, prompt: str, **kwargs) -> str:
        """
        Generate text completion using Nebius AI API.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
                      task_type: Type of task (e.g., "resume_parsing")
            
        Returns:
            Generated text response
        """
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        task_type = kwargs.get('task_type', 'general')
        
        # Log the task type for debugging
        self.logger.info(f"Nebius AI generating completion for task type: {task_type}")
        
        # Add system message for resume parsing tasks to improve context
        messages = []
        
        if task_type == "resume_parsing":
            # Add a system message for resume parsing tasks
            messages.append({
                "role": "system",
                "content": "You are an expert resume parser. Extract detailed, accurate information from resumes in a structured format. Be precise and thorough in your extraction."
            })
        
        # Add the user message with the prompt
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        async def make_api_call():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                response = await client.post(
                    f"{self.base_url}chat/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        
        success, response_text, exception = await self._retry_with_backoff(make_api_call)
        
        if not success:
            self.logger.error(f"Failed to generate completion after retries: {exception}")
            raise ParsingError(f"Failed to generate completion: {exception}")
        
        return response_text

    async def generate_text(self, prompt: str, **kwargs) -> str:
        """
        Generate text using Nebius AI API - compatibility method for resume parsing.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            Generated text response
        """
        return await self.generate_completion(prompt, **kwargs)
    
    def _extract_json_from_text(self, text: str) -> dict:
        """
        Extract JSON from text that might contain non-JSON elements.
        
        Args:
            text: Text that may contain JSON
            
        Returns:
            Extracted JSON as a dictionary
        """
        if not text:
            self.logger.warning("Empty text provided to JSON extraction")
            return {}
            
        # Try to find a JSON object enclosed in braces using a more robust approach
        # Count braces to avoid unbalanced parenthesis errors
        brace_count = 0
        start_pos = -1
        json_objects = []
        
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_pos = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_pos != -1:
                    json_objects.append(text[start_pos:i+1])
        
        if json_objects:
            # Use the first JSON object found
            json_str = json_objects[0]
            try:
                return json.loads(json_str)
            except Exception as e:
                self.logger.warning(f"Failed to parse JSON: {e}")
                return {}
        
        # Try to parse the entire text as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Last resort: Try to fix common JSON formatting issues
            try:
                # Replace single quotes with double quotes (common LLM mistake)
                fixed_text = re.sub(r"'([^']*)'\s*:\s*", r'"\1": ', text)
                fixed_text = re.sub(r":\s*'([^']*)'(,|})", r': "\1"\2', fixed_text)
                
                # Find what looks like a JSON object using a more robust approach
                # Count braces to avoid unbalanced parenthesis errors
                brace_count = 0
                start_pos = -1
                json_objects = []
                
                for i, char in enumerate(fixed_text):
                    if char == '{':
                        if brace_count == 0:
                            start_pos = i
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0 and start_pos != -1:
                            json_objects.append(fixed_text[start_pos:i+1])
                
                if json_objects:
                    return json.loads(json_objects[0])
            except Exception:
                pass
            
            self.logger.error(f"Failed to extract JSON from text: {text[:100]}...")
            return {}
    
    async def extract_resume_data(self, text: str, schema_prompt: str = None) -> dict:
        """
        Extract structured resume data from text using Nebius AI.
        
        Args:
            text: Resume text to parse
            schema_prompt: Optional schema prompt for extraction
            
        Returns:
            Dictionary containing structured resume data
        """
        if not schema_prompt:
            schema_prompt = """
            Extract structured information from the following resume text. Return a JSON object with the following structure:
            {
                "personal_info": {
                    "name": "string",
                    "email": "string", 
                    "phone": "string",
                    "location": "string",
                    "linkedin": "string",
                    "github": "string",
                    "website": "string",
                    "summary": "string"
                },
                "experience": [
                    {
                        "company": "string",
                        "title": "string", 
                        "start_date": "string",
                        "end_date": "string",
                        "location": "string",
                        "description": "string",
                        "highlights": ["string"]
                    }
                ],
                "education": [
                    {
                        "institution": "string",
                        "degree": "string",
                        "field_of_study": "string", 
                        "start_date": "string",
                        "end_date": "string",
                        "gpa": "string",
                        "location": "string"
                    }
                ],
                "skills": [
                    {
                        "name": "string",
                        "category": "string"
                    }
                ],
                "projects": [
                    {
                        "name": "string",
                        "description": "string",
                        "start_date": "string",
                        "end_date": "string",
                        "url": "string",
                        "technologies": ["string"]
                    }
                ],
                "certifications": [
                    {
                        "name": "string",
                        "issuer": "string",
                        "date": "string",
                        "url": "string"
                    }
                ],
                "languages": [
                    {
                        "name": "string",
                        "proficiency": "string"
                    }
                ]
            }
            
            Resume text:
            """
        
        full_prompt = schema_prompt + text
        
        try:
            response = await self.generate_completion(full_prompt)
            return self._extract_json_from_text(response)
        except Exception as e:
            self.logger.error(f"Error extracting resume data: {str(e)}")
            raise ParsingError(f"Failed to extract resume data: {str(e)}")
    
    async def parse_resume_section(self, section_type: str, section_content: str) -> dict:
        """
        Parse a specific section of a resume using Nebius AI.
        
        Args:
            section_type: Type of resume section (e.g., 'experience', 'education')
            section_content: Text content of the section
            
        Returns:
            Dictionary containing parsed section data
        """
        self.logger.info(f"Parsing resume section: {section_type}")
        
        prompt = f"""
        Parse the following {section_type} section from a resume and return structured data.
        
        Return ONLY a valid JSON object with the key "{section_type}" containing the parsed data.
        
        {section_type} section content:
        ---
        {section_content}
        ---
        """
        
        try:
            # Using task_type="resume_parsing" to ensure Nebius AI is used
            response = await self.generate_completion(
                prompt,
                max_tokens=1000,
                temperature=0.1,
                task_type="resume_parsing"
            )
            
            # Extract JSON from response using a more robust approach
            # Count braces to avoid unbalanced parenthesis errors
            brace_count = 0
            start_pos = -1
            json_objects = []
            
            for i, char in enumerate(response):
                if char == '{':
                    if brace_count == 0:
                        start_pos = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_pos != -1:
                        json_objects.append(response[start_pos:i+1])
            
            if json_objects:
                json_str = json_objects[0]
                return json.loads(json_str)
            else:
                # Try to parse the entire response as JSON
                return json.loads(response)
                
        except Exception as e:
            self.logger.error(f"Error parsing resume section {section_type}: {str(e)}")
            return {section_type: []}
    
    async def is_available(self) -> bool:
        """
        Check if the Nebius AI service is available.
        
        Returns:
            True if service is available, False otherwise
        """
        try:
            # Simple test call
            test_response = await self.generate_completion("Hello", max_tokens=10)
            return len(test_response) > 0
        except Exception as e:
            self.logger.warning(f"Nebius AI service not available: {str(e)}")
            return False

def get_nebius_ai_service(config_path: Optional[str] = None) -> "NebiusAIService":
    """
    Factory function to create a NebiusAIService instance.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Configured NebiusAIService instance
    """
    try:
        from backend.utils.config import get_settings
        settings = get_settings()
        
        config = {
            "nebius_base_url": settings.nebius_base_url,
            "model": settings.nebius_model,
            "api_key": settings.nebius_api_key,
            "timeout": settings.nebius_timeout,
            "temperature": settings.nebius_temperature,
            "max_tokens": settings.nebius_max_tokens,
        }
        
        logger.info(f"Loaded Nebius AI configuration from settings")
        return NebiusAIService(config)
        
    except Exception as e:
        logger.error(f"Error loading Nebius AI configuration from settings: {e}")
        
        # Try to load from config.json with environment variable substitution
        try:
            config_file_path = config_path or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.json')
            if os.path.exists(config_file_path):
                with open(config_file_path, 'r') as f:
                    config = json.load(f)
                    # Handle environment variable substitution
                    for key, value in config.items():
                        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                            env_var = value[2:-1]  # Remove ${ and }
                            config[key] = os.environ.get(env_var, "")
                            logger.info(f"Substituted {key} with environment variable {env_var}")
                    logger.info(f"Loaded Nebius AI configuration from {config_file_path}")
                    return NebiusAIService(config)
        except Exception as config_error:
            logger.error(f"Error loading from config file: {config_error}")
        
        # Fallback to environment variables
        config = {
            "nebius_base_url": os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/"),
            "model": os.environ.get("NEBIUS_MODEL", "microsoft/phi-4"),
            "api_key": os.environ.get("NEBIUS_API_KEY", ""),
            "timeout": float(os.environ.get("NEBIUS_TIMEOUT", "30.0")),
            "temperature": float(os.environ.get("NEBIUS_TEMPERATURE", "0.1")),
            "max_tokens": int(os.environ.get("NEBIUS_MAX_TOKENS", "500")),
        }
        
        logger.info(f"Using fallback configuration from environment variables")
        return NebiusAIService(config) 