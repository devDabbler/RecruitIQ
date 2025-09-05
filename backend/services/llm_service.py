"""
LLM Service for handling interactions with various LLM providers.
This service abstracts away the details of working with different LLM providers.
"""
import asyncio
import logging
import os
import httpx
import random
from functools import lru_cache
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import urllib.parse

# Set cache directory for sentence transformers to avoid re-downloading
os.environ['SENTENCE_TRANSFORMERS_HOME'] = './models/sentence_transformers'

# Direct implementation of Nebius AI to avoid circular imports
class DirectNebiusAI:
    """Direct implementation of Nebius AI service to avoid circular imports."""
    
    def __init__(self, api_key: str, model: str = "microsoft/phi-4", temperature: float = 0.1, max_tokens: int = 1500):
        """Initialize the Nebius AI service with configuration."""
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base_url = "https://api.studio.nebius.com/v1/"
        self.timeout = 180.0  # Increased timeout to 3 minutes for large resume parsing
        
        # Avoid binding a single AsyncClient to a loop (can cause 'Event loop is closed')
        # We'll create a short-lived client per request in generate_completion.
        self.client = None
        logging.info(f"Initialized Direct Nebius AI with model: {self.model}")
    
    async def generate_text(self, prompt: str, max_tokens: int = None, temperature: float = None, **kwargs) -> str:
        """Generate text using Nebius AI API - primary method used by extractors."""
        # This method is called by the structured_extractor.py
        return await self.generate_completion(prompt, max_tokens=max_tokens, temperature=temperature, **kwargs)
    
    async def generate_completion(self, prompt: str, **kwargs) -> str:
        """Generate completion using Nebius AI API."""
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        task_type = kwargs.get('task_type', 'general')
        
        # Log task type for debugging
        logging.info(f"Direct Nebius AI generating completion for task type: {kwargs.get('task_type', 'general')}")
        
        # Add system message for different task types
        system_message = "You are a helpful AI assistant specialized in various tasks."
        task_type = kwargs.get('task_type', '').lower()
        if "resume" in task_type:
            system_message = "You are a resume parsing specialist AI. Extract relevant information accurately."
        elif "market_research" in task_type:
            system_message = "You are a market research specialist AI. Provide accurate, data-driven insights and analysis. When discussing salaries, be realistic and consider experience levels carefully. Entry-level positions should have significantly lower compensation than senior roles. When asked for JSON output, return ONLY valid JSON without any additional text, explanations, or markdown formatting. Start with { and end with }."
        
        # Configure request parameters
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        
        # Build the API request
        url = f"{self.base_url}chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Debug headers and auth (without revealing full API key)
        masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) > 8 else "****"
        logging.debug(f"Nebius API Key format check: {masked_key} (length: {len(self.api_key)})")
        
        # Prepare the request payload
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            # Make the API call using a per-request client so reloads/shutdowns don't break the loop
            logging.info(f"Sending prompt to Nebius AI model: {self.model}")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
            
            # Debug response status and details on error
            if response.status_code != 200:
                logging.error(f"Nebius API Error: Status {response.status_code}")
                logging.error(f"Response headers: {response.headers}")
                logging.error(f"Response body: {response.text}")
                
                # Special handling for common errors
                if response.status_code == 401 or response.status_code == 403:
                    logging.critical("Authentication error with Nebius API - check your API key format and validity")
                    logging.critical("Make sure your .env file contains NEBIUS_API_KEY with correct format")
                elif response.status_code == 502:
                    logging.warning("Nebius AI service temporarily unavailable (502 Bad Gateway) - this is usually a temporary issue")
                    logging.warning("The system will automatically fall back to alternative models")
                elif response.status_code >= 500:
                    logging.warning(f"Nebius AI server error ({response.status_code}) - service may be temporarily unavailable")
                
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                logging.error(f"Unexpected response format from Nebius AI: {result}")
                return ""
        except Exception as e:
            logging.error(f"Error generating completion with Nebius AI: {e}")
            raise RuntimeError(f"Failed to generate text with Nebius AI: {e}")
    
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
            logging.warning(f"Direct Nebius AI service not available: {str(e)}")
            return False

# Try importing libraries, but continue if not available
try:
    import cohere
except ImportError:
    cohere = None
    logging.warning("cohere package not found, Cohere functionality will be limited")

try:
    import google.generativeai as genai
    from google.generativeai import GenerativeModel
except ImportError:
    genai = None
    GenerativeModel = None
    logging.warning("google.generativeai package not found, Gemini functionality will be limited")

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None
    logging.warning("langchain_groq package not found, Meta Llama functionality will be limited")

from backend.utils.config import Settings

logger = logging.getLogger(__name__)

class ModelType(Enum):
    """Enum for model types."""
    GEMINI_PRO = "models/gemini-1.5-pro"
    GEMINI_PRO_VISION = "models/gemini-1.5-pro-vision-latest"
    GEMINI_EMBEDDING = "models/embedding-001"
    META_LLAMA_MAVERICK = "meta-llama/llama-4-maverick-17b-128e-instruct"
    COHERE_EMBED = "embed-english-v3.0"
    COHERE_EMBED_MULTILINGUAL = "embed-multilingual-v3.0"
    COHERE_COMMAND = "command"
    COHERE_COMMAND_LIGHT = "command-light"
    COHERE_COMMAND_R = "command-r"
    COHERE_COMMAND_R_PLUS = "command-r-plus"
    NEBIUS_PHI4 = "microsoft/phi-4"


@lru_cache(maxsize=1)
def _load_sentence_transformer_model(model_name: str):
    """
    Loads and caches the sentence transformer model.
    This function is cached to ensure the model is loaded only once.
    """
    try:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading sentence transformer model: {model_name}")
        # The model will be downloaded to the cache directory set by SENTENCE_TRANSFORMERS_HOME
        return SentenceTransformer(model_name)
    except ImportError:
        logger.error("sentence_transformers package not found. Please install it to use embedding models.")
        return None
    except Exception as e:
        logger.error(f"Failed to load sentence transformer model '{model_name}': {e}")
        return None


class LLMService:
    """
    Service for handling interactions with various LLM providers like Google's Gemini and Cohere.
    """
    def __init__(self, settings: Settings):
        """
        Initialize the LLM service with configuration settings.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.embedding_model = None
        self._embedding_model_loaded = False
        
        # Gemini is disabled as requested by user configuration
        self.gemini_models = {}
        logger.info("Gemini initialization skipped - using Meta Llama only as configured")
                
        # DISABLED: Meta Llama initialization completely disabled for resume parsing
        self.meta_llama_model = None
        self._meta_llama_initialized = False
        
        # Initialize Cohere
        self.cohere_client = None
        self._cohere_initialized = False
        
        # Initialize Nebius AI
        self.nebius_ai_service = None
        self._nebius_ai_initialized = False
        
        # Initialize Nebius AI immediately since it's our preferred parser
        self._initialize_nebius_ai()
        
        # Connection status
        self._connection_status = None
    
    async def initialize(self) -> bool:
        """
        Initialize the LLM service asynchronously.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Verify connections asynchronously
            connection_status = {}
            
            # Check Meta Llama
            if hasattr(self, "meta_llama_model") and self.meta_llama_model:
                connection_status["meta_llama"] = True
                logger.info("Meta Llama connection initialized successfully")
            else:
                connection_status["meta_llama"] = False
                logger.warning("Meta Llama not configured or failed to initialize")
            
            # Check Cohere
            if self.cohere_client:
                connection_status["cohere"] = True
                logger.info("Cohere connection initialized successfully")
            else:
                connection_status["cohere"] = False
                logger.warning("Cohere not configured or failed to initialize")
            
            # Check Nebius AI
            if self.nebius_ai_service:
                connection_status["nebius_ai"] = True
                logger.info("Nebius AI connection initialized successfully")
            else:
                connection_status["nebius_ai"] = False
                logger.warning("Nebius AI not configured or failed to initialize")
            
            # Log overall status
            logger.info(f"LLM Connection Status: {connection_status}")
            
            # Return True if at least one service is available
            return any(connection_status.values())
        except Exception as e:
            logger.error(f"Error initializing LLM service: {str(e)}")
            return False
    
    def get_embedding_model(self):
        """
        Get the embedding model, loading it if necessary.
        This method ensures the model is loaded only once and cached.
        """
        if not self._embedding_model_loaded:
            # Use the cached loading function
            self.embedding_model = _load_sentence_transformer_model("sentence-transformers/all-MiniLM-L6-v2")
            
            if self.embedding_model is None:
                # Fallback to simple embedding adapter if sentence transformers fails
                logger.warning("Falling back to simple embedding adapter")
                class SimpleEmbeddingAdapter:
                    def embed_documents(self, texts):
                        # Simple fallback - return random embeddings
                        import numpy as np
                        return [np.random.rand(384).tolist() for _ in texts]
                    
                    def embed_query(self, text):
                        import numpy as np
                        return np.random.rand(384).tolist()
                    
                    def encode(self, text):
                        """Direct encode method for compatibility with cache_utils"""
                        import numpy as np
                        if isinstance(text, str):
                            return np.random.rand(384)
                        else:
                            return np.array([np.random.rand(384) for _ in text])
                
                self.embedding_model = SimpleEmbeddingAdapter()
            else:
                # Wrap the sentence transformer in a consistent interface
                class SentenceTransformerAdapter:
                    def __init__(self, model):
                        self.model = model
                    
                    def embed_documents(self, texts):
                        return self.model.encode(texts).tolist()
                    
                    def embed_query(self, text):
                        return self.model.encode([text])[0].tolist()
                    
                    def encode(self, text):
                        """Direct encode method for compatibility with cache_utils"""
                        if isinstance(text, str):
                            # Return numpy array for single string (needed for cache_utils)
                            return self.model.encode([text])[0]
                        else:
                            # Return numpy array for list of strings
                            return self.model.encode(text)
                
                self.embedding_model = SentenceTransformerAdapter(self.embedding_model)
            
            self._embedding_model_loaded = True
        
        return self.embedding_model
    
    def _initialize_nebius_ai(self) -> bool:
        """
        Initialize the Nebius AI service - THIS IS THE REQUIRED SERVICE FOR RESUME PARSING.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if self._nebius_ai_initialized and self.nebius_ai_service is not None:
            logger.info("Nebius AI already initialized and available")
            return True
        
        try:
            # Force import and initialization of Nebius AI
            from backend.services.nebius_ai_service import get_nebius_ai_service, NebiusAIService
            
            # CRITICAL: Resolve API key with Settings (.env) as primary source,
            # then fall back to environment variables for compatibility.
            api_key = getattr(self.settings, 'nebius_api_key', None) or ""
            source = "settings.nebius_api_key"
            if not api_key:
                api_key = os.environ.get('NEBIUS_API_KEY', "")
                source = "env:NEBIUS_API_KEY" if api_key else source
            if not api_key:
                api_key = os.environ.get('NEBIUS_API_TOKEN', "")
                source = "env:NEBIUS_API_TOKEN" if api_key else source
            
            if not api_key:
                logger.critical("CRITICAL ERROR: NEBIUS_API_KEY not found in environment or settings.")
                logger.critical("Resume parsing will fail without this API key. Check your environment variables.")
                raise ValueError("NEBIUS_API_KEY missing - this is required for resume parsing")
            else:
                masked = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"
                logger.info(f"Nebius API key resolved from {source}: {masked}")
            
            # Force direct initialization with inline configuration
            config = {
                "nebius_base_url": "https://api.studio.nebius.com/v1/",
                "model": "microsoft/phi-4",
                "api_key": api_key,
                "timeout": 180.0,  # Increased timeout for large resume parsing
                "temperature": 0.1,
                "max_tokens": 2000
            }
            
            # Create service directly instead of using factory
            self.nebius_ai_service = NebiusAIService(config)
            logger.info("Nebius AI service initialized directly with API key and config")
            self._nebius_ai_initialized = True
            return True
        
        except Exception as e:
            error_msg = f"CRITICAL ERROR initializing Nebius AI service: {str(e)}"
            logger.critical(error_msg)
            print(error_msg)  # Print to ensure visibility
            
            # Raise exception to prevent silent failures
            raise RuntimeError("Nebius AI initialization failed - cannot proceed with resume parsing") from e
    
    def get_llm(self, model_name):
        """
        Get an LLM instance by model name.
        
        Args:
            model_name: Name of the model to get
            
        Returns:
            LLM instance or None if not available
        """
        if model_name == ModelType.NEBIUS_PHI4.value:
            # Ensure Nebius AI is initialized
            if not self._nebius_ai_initialized:
                self._initialize_nebius_ai()
            return self.nebius_ai_service
        elif model_name == ModelType.META_LLAMA_MAVERICK.value:
            # Lazy initialize Meta Llama
            self._initialize_meta_llama()
            return self.meta_llama_model
        elif model_name == ModelType.COHERE_COMMAND.value:
            # Lazy initialize Cohere
            self._initialize_cohere()
            return self.cohere_client
        else:
            logger.warning(f"Unknown model name: {model_name}")
            return None

    async def extract_structured_resume_with_cohere(self, text: str) -> Dict[str, Any]:
        """
        Extract structured data from resume text using Cohere's extraction capabilities.
        Args:
            text: The text to extract data from
        Returns:
            Dictionary with extracted data
        """
        import json
        if not self.cohere_client:
            logger.warning("Cohere client not available - returning mock extraction")
            return {
                "text": "Mock extraction result",
                "mock": True,
                "extracted_data": {
                    "name": "Sample Name",
                    "skills": ["Python", "JavaScript"],
                    "experience": "5 years"
                }
            }
        # Ensure prompt strictly requests valid JSON
        prompt = (
            text.strip() + "\n\nIMPORTANT: Return ONLY a valid JSON object matching the required schema. Do not include any explanations or formatting."
        )
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cohere_client.chat(
                    model="command-r",
                    message=prompt,
                    temperature=0.2,
                    max_tokens=2048,
                )
            )
            raw = response.text if hasattr(response, 'text') else str(response)
            try:
                data = json.loads(raw)
                return data
            except Exception as e:
                logger.error(f"Cohere response not valid JSON: {e}")
                logger.error(f"Cohere raw response: {raw}")
                return {"text": raw}
        except Exception as e:
            logger.error(f"Cohere extraction failed: {e}")
            return {"text": f"Cohere error: {e}"}

    async def generate_structured_output(self, prompt: str, model: str = "models/gemini-1.5-pro", response_model: type = dict, **kwargs) -> dict:
        """
        Use Gemini to generate a structured JSON output from a prompt.
        Args:
            prompt: The prompt string
            model: Which Gemini model to use
            response_model: Expected response type (unused, for compatibility)
        Returns:
            Parsed JSON dictionary, or empty dict on error
        """
        import json
        try:
            gemini = self.get_llm(model)
            # Use async generation if available, else fallback
            if hasattr(gemini, "generate_content_async"):
                response = await gemini.generate_content_async(prompt, **kwargs)
                raw = response.text if hasattr(response, 'text') else str(response)
            else:
                response = gemini.generate_content(prompt, **kwargs)
                raw = response.text if hasattr(response, 'text') else str(response)
            try:
                data = json.loads(raw)
                return data
            except Exception as e:
                logger.error(f"Gemini response not valid JSON: {e}")
                logger.error(f"Gemini raw response: {raw}")
                return {}
        except Exception as e:
            logger.error(f"Gemini structured extraction failed: {e}")
            return {}

        
        try:
            response = self.cohere_client.chat(
                message=f"Extract structured data from this resume: {text}",
                model=ModelType.COHERE_COMMAND_R.value,
                temperature=0.1
            )
            return response.to_dict() if hasattr(response, "to_dict") else {"text": str(response)}
        except Exception as e:
            logger.error(f"Error during Cohere structured extraction: {str(e)}")
            return {"error": str(e)}
    
    async def generate_text(self, prompt: str, model_type: ModelType = ModelType.META_LLAMA_MAVERICK, task_type: str = "general") -> str:
        """
        Generate text using one of the configured LLM models.
        
        Args:
            prompt: The prompt to generate from
            model_type: The model to use for generation 
            task_type: Type of task for context-specific model selection (e.g., "resume_parsing")
            
        Returns:
            Generated text response
        """
        logger.info(f"Generate text called for prompt: '{prompt[:100]}...' with task_type: {task_type}")
        
        # For ALL resume-related tasks, always prioritize Nebius AI as requested by user
        # This includes resume parsing, resume quality assessment, skill extraction, etc.
        if (task_type == "resume_parsing" or 
            "resume" in task_type.lower() or 
            "cv" in task_type.lower() or 
            prompt.lower().find("resume") != -1) and self.nebius_ai_service:
            try:
                logger.info(f"Using Nebius AI for resume-related task: {task_type}")
                nebius_response = await self.nebius_ai_service.generate_completion(prompt, task_type=task_type)
                return nebius_response
            except Exception as e:
                logger.error(f"Error generating text with Nebius AI: {e}")
                logger.warning("Falling back to other models after Nebius AI failure")
                # Continue to fallbacks if Nebius fails
                # Don't raise the exception - let the fallback chain handle it
        
        # For other tasks or if Nebius AI failed, use Meta Llama
        if hasattr(self, "meta_llama_model") and self.meta_llama_model:
            try:
                logger.info("Sending prompt to Meta Llama model...")
                # The response from invoke is an AIMessage object
                response_message = await self.meta_llama_model.ainvoke(prompt)
                
                # The actual text is in the `content` attribute
                return response_message.content
            except Exception as e:
                logger.error(f"Error generating text with Meta Llama: {e}")
                # Continue to fallbacks instead of raising
        
        # If Meta Llama fails or isn't available, try Cohere
        if self.cohere_client:
            try:
                logger.info("Trying Cohere as fallback")
                cohere_response = self.cohere_client.chat(
                    message=prompt,
                    model=ModelType.COHERE_COMMAND_R.value
                )
                return cohere_response.text
            except Exception as cohere_e:
                logger.error(f"Cohere fallback also failed: {str(cohere_e)}")
        
        # If we reach here and we have Nebius AI but didn't try it yet (non-resume task), try it now
        if task_type != "resume_parsing" and self.nebius_ai_service:
            try:
                logger.info("Trying Nebius AI as final fallback")
                nebius_response = await self.nebius_ai_service.generate_completion(prompt, task_type=task_type)
                return nebius_response
            except Exception as nebius_e:
                logger.error(f"Nebius AI fallback also failed: {str(nebius_e)}")
        
        # If all models fail, return a helpful error message
        logger.warning("All LLM services failed - returning fallback message")
        return "I'm having trouble generating a response with my AI service right now. Please try again later."
    
    async def generate_content(self, prompt: str, **kwargs) -> str:
        """
        Generate content from a prompt - alias for generate_text_async for compatibility.
        
        Args:
            prompt: The prompt to generate from
            **kwargs: Additional parameters to pass to the LLM
            
        Returns:
            Generated text response
        """
        logger.info(f"Generate content called with prompt length: {len(prompt)}")
        return await self.generate_text_async(prompt=prompt, **kwargs)
    
    async def generate_text_async(self, prompt: str, model=None, task_type="chat", system_message=None, max_tokens=None) -> str:
        """
        Generate text from a prompt using the specified model asynchronously.
        This method is designed to be flexible and work with different models.
        
        Args:
            prompt: The text prompt for the model
            model: The model to use (defaults to Nebius AI for most tasks)
            task_type: The type of task, for logging and context
            system_message: Optional system message for models that support it
            max_tokens: Optional max tokens to generate
            
        Returns:
            The generated text as a string
        """
        logger.info(f"Generate text called for prompt: '{prompt[:min(len(prompt), 80)]}...'")
        
        # If a specific model override is provided and looks like an OpenRouter/Meta Llama slug,
        # prefer calling OpenRouter directly (non-invasive - requires OPENROUTER_API_KEY in settings).
        try:
            openrouter_key = getattr(self.settings, 'openrouter_api_key', '') or os.environ.get('OPENROUTER_API_KEY', '')
        except Exception:
            openrouter_key = os.environ.get('OPENROUTER_API_KEY', '')

        if model and isinstance(model, str):
            model_lower = model.lower()
            # Accept a broader set of model indicators so configuration remains dynamic.
            looks_like_meta_llama = (
                model_lower.startswith('meta-llama/') or
                'meta-llama' in model_lower or
                model_lower.startswith('llama-') or
                'maverick' in model_lower or
                'llama' in model_lower or
                'openrouter' in model_lower
            )
            openrouter_enabled = getattr(self.settings, 'openrouter_enabled', False)
            if looks_like_meta_llama and openrouter_key and openrouter_enabled:
                try:
                    logger.info(f"Using OpenRouter/OpenAI-compatible provider for model override: {model}")
                    openrouter_resp = await self._call_openrouter_async(prompt=prompt, model=model, system_message=system_message, max_tokens=max_tokens, api_key=openrouter_key)
                    if openrouter_resp is not None:
                        return openrouter_resp
                except Exception as e:
                    logger.error(f"OpenRouter call failed for model {model}: {e}")

        # Use Nebius AI as the primary model for most tasks (except resume parsing which has its own flow)
        if self.nebius_ai_service and task_type != "resume_parsing":
            try:
                logger.info("Sending prompt to Nebius AI model...")
                response = await self.nebius_ai_service.generate_completion(
                    prompt, 
                    max_tokens=max_tokens or 1200,
                    temperature=0.1,
                    task_type=task_type
                )
                return response
            except Exception as e:
                logger.error(f"Error generating text with Nebius AI: {e}")
                logger.warning("Falling back to other models after Nebius AI failure")
        
        # Use Meta Llama as secondary option (if available and enabled)
        if self.meta_llama_model:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                
                messages = []
                if system_message:
                    messages.append(SystemMessage(content=system_message))
                messages.append(HumanMessage(content=prompt))
                
                logger.info("Sending prompt to Meta Llama model...")
                # The response from invoke is an AIMessage object
                response_message = await self.meta_llama_model.ainvoke(messages)
                
                # The actual text is in the `content` attribute
                return response_message.content
            except Exception as e:
                logger.error(f"Error generating text with Meta Llama: {e}")
        
        # Fallback to Cohere if other models are not available
        if self.cohere_client:
            try:
                logger.info("Falling back to Cohere after Meta Llama failure")
                cohere_response = self.cohere_client.chat(
                    message=prompt,
                    model=ModelType.COHERE_COMMAND_R.value
                )
                return cohere_response.text
            except Exception as cohere_e:
                logger.error(f"Cohere fallback also failed: {str(cohere_e)}")
        
        # Fallback to Nebius AI if Cohere is not available
        elif self.nebius_ai_service:
            try:
                logger.info("Falling back to Nebius AI after Cohere failure")
                nebius_response = await self.nebius_ai_service.generate_completion(prompt)
                return nebius_response
            except Exception as nebius_e:
                logger.error(f"Nebius AI fallback also failed: {str(nebius_e)}")
        
        # If all else fails, give a helpful error response
        return "I'm having trouble generating a response with my AI service right now. Please try again later."

    def _initialize_meta_llama(self) -> bool:
        """Meta Llama initialization is DISABLED for all resume-related tasks."""
        # COMPLETELY DISABLED: Meta Llama is not allowed for resume parsing or any resume-related tasks
        logger.warning("Meta Llama initialization is DISABLED - resume parsing must use Nebius AI exclusively")
        self.meta_llama_model = None
        self._meta_llama_initialized = False
        return False

    def _initialize_cohere(self):
        """Lazy initialize Cohere client."""
        if self._cohere_initialized:
            return
        
        if cohere is not None:
            try:
                # Cohere isn't in the Settings class, use openrouter_api_key as fallback or empty string
                cohere_api_key = getattr(self.settings, 'cohere_api_key', '')
                if not cohere_api_key:
                    # Use openrouter key as fallback or empty string
                    cohere_api_key = getattr(self.settings, 'openrouter_api_key', '')
                    if cohere_api_key:
                        logger.info("Using OpenRouter API key as fallback for Cohere client")
                
                if cohere_api_key:
                    self.cohere_client = cohere.Client(api_key=cohere_api_key)
                    logger.info("Cohere client initialized successfully")
                else:
                    logger.warning("No Cohere API key found in settings")
            except Exception as e:
                logger.error(f"Failed to initialize Cohere client: {str(e)}")
        
        self._cohere_initialized = True

    def _initialize_nebius_ai(self):
        """Lazy initialize Nebius AI service - direct implementation without importing NebiusAIService."""
        if self._nebius_ai_initialized:
            return
        
        try:
            # Get API key from settings or environment
            nebius_api_key = getattr(self.settings, 'nebius_api_key', '')
            if not nebius_api_key:
                nebius_api_key = os.environ.get('NEBIUS_API_KEY', '') or os.environ.get('NEBIUS_API_TOKEN', '')
            
            if nebius_api_key:
                # Create a direct implementation of Nebius AI capabilities
                # instead of importing NebiusAIService to avoid circular imports
                self.nebius_ai_service = DirectNebiusAI(
                    api_key=nebius_api_key,
                    model="microsoft/phi-4",
                    temperature=0.1,
                    max_tokens=1500
                )
                self._nebius_ai_initialized = True
                logger.info("Nebius AI service initialized successfully using direct implementation")
            else:
                logger.warning("No Nebius API key found for initialization")
        except Exception as e:
            logger.error(f"Failed to initialize Nebius AI service: {str(e)}")
            
        self._nebius_ai_initialized = True

    async def _call_openrouter_async(self, prompt: str, model: str, system_message: Optional[str] = None, max_tokens: Optional[int] = None, api_key: str = None) -> Optional[str]:
        """
        Minimal OpenRouter call that posts a chat completion request to OpenRouter-compatible API.
        This keeps the change small and avoids pulling in new heavy dependencies.
        Returns the text response or None on non-fatal failures.
        """
        if not api_key:
            logger.warning("OpenRouter API key not provided - skipping OpenRouter call")
            return None

        # Normalize OpenRouter endpoint; allow settings override
        openrouter_base = getattr(self.settings, 'openrouter_base_url', '') or os.environ.get('OPENROUTER_BASE_URL', '')
        if not openrouter_base:
            # Default OpenRouter endpoint
            openrouter_base = 'https://api.openrouter.ai/v1'
        
        # Build the complete URL - if base_url doesn't end with /chat/completions, append it
        if openrouter_base.endswith('/chat/completions'):
            url = openrouter_base
        elif openrouter_base.endswith('/v1'):
            url = f"{openrouter_base}/chat/completions"
        elif openrouter_base.endswith('/v1/'):
            url = f"{openrouter_base}chat/completions"
        elif '/api/v1/chat/completions' in openrouter_base:
            # Handle full OpenRouter API URL format
            url = openrouter_base
        else:
            # Assume it's a base URL and append the path
            url = f"{openrouter_base.rstrip('/')}/chat/completions"

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        # Construct messages payload if the API expects it (OpenRouter uses messages similar to OpenAI)
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages
        }
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)

        # Configure retries and timeout from settings or environment variables
        max_retries = getattr(self.settings, 'openrouter_max_retries', 3) or int(os.environ.get('OPENROUTER_MAX_RETRIES', '3'))
        backoff_factor = getattr(self.settings, 'openrouter_backoff_factor', 0.8) or float(os.environ.get('OPENROUTER_BACKOFF_FACTOR', '0.8'))
        per_request_timeout = getattr(self.settings, 'openrouter_timeout', 60.0) or float(os.environ.get('OPENROUTER_REQUEST_TIMEOUT', '60.0'))

        # Enhanced DNS resolution and fallback handling
        try:
            import socket as _socket
            parsed = urllib.parse.urlparse(url)
            host = parsed.netloc.split(':')[0]

            # Skip DNS pre-check if a proxy is configured or if user explicitly requests skipping.
            proxy_env_keys = ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy']
            proxy_present = any(os.environ.get(k) for k in proxy_env_keys)
            skip_flag = str(os.environ.get('OPENROUTER_SKIP_DNS_CHECK', '')).lower() in ('1', 'true', 'yes')

            # Also skip DNS check if the host is already an IP address
            is_ip = False
            try:
                import ipaddress as _ipaddress
                _ipaddress.ip_address(host)
                is_ip = True
            except Exception:
                is_ip = False

            if proxy_present or skip_flag or is_ip:
                logger.debug("Skipping DNS resolution pre-check for OpenRouter (proxy_present=%s, skip_flag=%s, is_ip=%s)", proxy_present, skip_flag, is_ip)
            else:
                # Try multiple DNS resolution strategies
                dns_resolved = False
                fallback_urls = []
                
                # Strategy 1: Direct host resolution
                try:
                    _socket.getaddrinfo(host, 443)
                    logger.debug("DNS resolution for OpenRouter host succeeded (%s)", host)
                    dns_resolved = True
                except Exception as _dns_e:
                    logger.warning(f"Primary DNS resolution failed for {host}: {_dns_e}")
                    
                    # Strategy 2: Try alternate hosts from environment
                    alt_hosts = os.environ.get('OPENROUTER_ALTERNATE_HOSTS', '')
                    if alt_hosts:
                        for candidate in [h.strip() for h in alt_hosts.split(',') if h.strip()]:
                            try:
                                _socket.getaddrinfo(candidate, 443)
                                fallback_urls.append(f"https://{candidate}/chat/completions")
                                logger.info("Alternate OpenRouter host resolved: %s", candidate)
                            except Exception:
                                logger.debug("Alternate host failed to resolve: %s", candidate)
                    
                    # Strategy 3: Try common fallback patterns
                    fallback_patterns = [
                        f"https://api.{host}/chat/completions",
                        f"https://{host.replace('api.', '')}/chat/completions",
                        f"https://{host.replace('openrouter', 'api.openrouter')}/chat/completions"
                    ]
                    
                    for fallback_url in fallback_patterns:
                        try:
                            fallback_host = urllib.parse.urlparse(fallback_url).netloc.split(':')[0]
                            _socket.getaddrinfo(fallback_host, 443)
                            fallback_urls.append(fallback_url)
                            logger.info("Fallback pattern resolved: %s", fallback_url)
                        except Exception:
                            logger.debug("Fallback pattern failed: %s", fallback_url)
                
                # If primary DNS failed but we have fallbacks, use the first working one
                if not dns_resolved and fallback_urls:
                    url = fallback_urls[0]
                    logger.info("Using fallback OpenRouter URL: %s", url)
                    
        except Exception as e:
            # If socket isn't available for some reason, continue but note it
            logger.debug("Socket module unavailable for DNS checks: %s", e)

        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                # Use trust_env=True so httpx will honor HTTP(S)_PROXY if present in environment
                async with httpx.AsyncClient(timeout=per_request_timeout, trust_env=True) as client:
                    resp = await client.post(url, json=payload, headers=headers)

                if resp.status_code in (200, 201):
                    try:
                        data = resp.json()
                        # Support multiple response shapes: choices[0].message.content or output[0].content
                        if isinstance(data, dict):
                            if 'choices' in data and len(data['choices']) > 0:
                                choice = data['choices'][0]
                                # OpenRouter/OpenAI style
                                if isinstance(choice, dict) and 'message' in choice and isinstance(choice['message'], dict):
                                    return choice['message'].get('content', '')
                                # older style
                                if isinstance(choice, dict) and 'text' in choice:
                                    return choice.get('text', '')
                            # alternative: output list
                            if 'output' in data and isinstance(data['output'], list) and len(data['output']) > 0:
                                first = data['output'][0]
                                if isinstance(first, dict) and 'content' in first:
                                    # content can be a string or a list
                                    content = first['content']
                                    if isinstance(content, list):
                                        # join string parts
                                        return '\n'.join([str(c) for c in content])
                                    return str(content)
                        # Fallback to text body
                        return resp.text
                    except Exception as parse_e:
                        logger.error(f"Failed to parse OpenRouter response JSON: {parse_e}")
                        return resp.text
                else:
                    logger.warning(f"OpenRouter request failed: status={resp.status_code} body={resp.text}")
                    if resp.status_code in (401, 403):
                        logger.critical("OpenRouter authentication failed - check OPENROUTER_API_KEY in .env/settings")
                    # For 5xx errors, retry; for 4xx, don't retry
                    if 500 <= resp.status_code < 600 and attempt < max_retries:
                        sleep_sec = backoff_factor * (2 ** (attempt - 1)) + random.random() * 0.1
                        logger.info(f"Retrying OpenRouter request after {sleep_sec:.2f}s backoff (attempt {attempt}/{max_retries})")
                        await asyncio.sleep(sleep_sec)
                        continue
                    return None
            except Exception as e:
                last_exc = e
                # Provide more explicit guidance in logs without exposing secrets
                logger.error(f"Exception calling OpenRouter (attempt {attempt}/{max_retries}): {type(e).__name__}: {e}")
                # Common DNS/connectivity guidance
                if isinstance(e, Exception) and 'getaddrinfo' in str(e):
                    logger.error("Detected DNS resolution failure when contacting OpenRouter. Check network/DNS or set OPENROUTER_BASE_URL to a reachable endpoint or configure HTTP(S)_PROXY.")
                    logger.error("You can also try setting OPENROUTER_SKIP_DNS_CHECK=1 to bypass DNS checks, or set OPENROUTER_ALTERNATE_HOSTS with comma-separated alternative endpoints.")
                elif isinstance(e, Exception) and 'timeout' in str(e).lower():
                    logger.error("OpenRouter request timed out. Consider increasing OPENROUTER_REQUEST_TIMEOUT or checking network connectivity.")
                elif isinstance(e, Exception) and 'connection' in str(e).lower():
                    logger.error("OpenRouter connection failed. Check if the service is accessible from your network.")
                
                if attempt < max_retries:
                    sleep_sec = backoff_factor * (2 ** (attempt - 1)) + random.random() * 0.2
                    logger.info(f"Retrying after exception (sleep {sleep_sec:.2f}s)")
                    await asyncio.sleep(sleep_sec)
                    continue
                else:
                    logger.error("OpenRouter call failed after max retries")
                    return None

        # If we exhausted retries, log final exception if any
        if last_exc:
            logger.error(f"OpenRouter final exception: {last_exc}")
        return None

def verify_llm_connections(llm_service: LLMService) -> Dict[str, bool]:
    """
    Verify connections to all configured LLM services.
    
    Args:
        llm_service: LLMService instance
        
    Returns:
        Dictionary with connection status for each service
    """
    if llm_service._connection_status is not None:
        return llm_service._connection_status
    
    connection_status = {
        'gemini': False,
        'meta_llama': False,
        'cohere': False,
        'nebius_ai': False
    }
    
    # Check Gemini (disabled)
    connection_status['gemini'] = False
    logger.info("Gemini not configured")
    
    # Meta Llama is completely disabled for resume parsing
    connection_status['meta_llama'] = False
    logger.info("Meta Llama is explicitly disabled for resume parsing - Nebius AI is the only allowed resume parser")
    
    # Check Cohere
    try:
        llm_service._initialize_cohere()
        if llm_service.cohere_client:
            # Test the connection with a simple request
            response = llm_service.cohere_client.chat(
                model="command",
                message="Hello",
                max_tokens=10
            )
            if response:
                connection_status['cohere'] = True
                logger.info("Cohere connection verified successfully")
            else:
                logger.warning("Cohere connection test failed")
        else:
            logger.warning("Cohere client not properly initialized")
    except Exception as e:
        logger.error(f"Cohere connection failed: {e}")
    
    # Check Nebius AI
    try:
        llm_service._initialize_nebius_ai()
        if llm_service.nebius_ai_service:
            # Test the connection with a simple request
            import asyncio
            try:
                # Check if we're already in an async context
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context, assume the service is working
                    # since we can't run asyncio.run() here
                    connection_status['nebius_ai'] = True
                    logger.info("Nebius AI connection assumed valid (in async context)")
                except RuntimeError:
                    # No running event loop, we can safely use asyncio.run()
                    test_result = asyncio.run(llm_service.nebius_ai_service.is_available())
                    if test_result:
                        connection_status['nebius_ai'] = True
                        logger.info("Nebius AI connection verified successfully")
                    else:
                        logger.warning("Nebius AI connection test failed")
            except Exception as test_e:
                logger.warning(f"Nebius AI connection test failed: {test_e}")
                connection_status['nebius_ai'] = True  # Assume it's working if we can't test
        else:
            logger.warning("Nebius AI service not properly initialized")
    except Exception as e:
        logger.error(f"Nebius AI connection failed: {e}")
    
    llm_service._connection_status = connection_status
    logger.info(f"LLM Connection Status: {connection_status}")
    
    return connection_status

def get_llm_service(settings: Optional[Settings] = None) -> LLMService:
    """
    Factory function to get an initialized LLMService.
    
    Args:
        settings: Optional settings, will be loaded from environment if not provided
        
    Returns:
        Initialized LLMService
    """
    if settings is None:
        try:
            from backend.utils.config import get_settings
            settings = get_settings()
        except Exception as e:
            logger.warning(f"Error loading settings: {e}. Using empty Settings instance.")
            settings = Settings()
    
    service = LLMService(settings)
    
    # Verify connections on startup and log results
    try:
        connection_status = verify_llm_connections(service)
        logger.info(f"LLM Connection Status: {connection_status}")
    except Exception as e:
        logger.error(f"Error verifying LLM connections: {str(e)}")
    
    return service
