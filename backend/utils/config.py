import os
from typing import Optional, ClassVar
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict, DotEnvSettingsSource
from dotenv import find_dotenv
import logging

# Load .env from the root directory
# load_dotenv(find_dotenv()) # REMOVED - Rely on Pydantic model_config

class Settings(BaseSettings):
    """Application settings loaded from environment variables using pydantic-settings."""
    
    # API Keys
    groq_api_key: str = Field(default=os.getenv("GROQ_API_KEY", ""))
    gemini_api_key: str = Field(default=os.getenv("GOOGLE_GEMINI_API_KEY", ""))
    cohere_api_key: str = Field(default=os.getenv("COHERE_API_KEY", ""))
    openrouter_api_key: str = Field(default=os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_default_model: str = Field(default=os.getenv("OPENROUTER_DEFAULT_MODEL", "meta-llama/llama-3.3-8b-instruct:free"))
    openrouter_base_url: str = Field(default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    openrouter_timeout: float = Field(default=float(os.getenv("OPENROUTER_TIMEOUT", "60.0")))
    openrouter_max_retries: int = Field(default=int(os.getenv("OPENROUTER_MAX_RETRIES", "3")))
    openrouter_backoff_factor: float = Field(default=float(os.getenv("OPENROUTER_BACKOFF_FACTOR", "0.8")))
    # Toggle to enable OpenRouter usage for assistant queries (keeps behavior dynamic)
    openrouter_enabled: bool = Field(default=os.getenv("OPENROUTER_ENABLED", "false").lower() == "true")
    
    # Google Custom Search keys (used by web_search_service)
    google_api_key: str = Field(default=os.getenv("GOOGLE_API_KEY", ""))
    google_cse_id: str = Field(default=os.getenv("GOOGLE_CSE_ID", ""))
    
    # Meta Llama Configuration
    meta_llama_enabled: bool = Field(default=os.getenv("META_LLAMA_ENABLED", "false").lower() == "true")
    meta_llama_model: str = Field(default=os.getenv("META_LLAMA_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct"))
    meta_llama_timeout: float = Field(default=float(os.getenv("META_LLAMA_TIMEOUT", "30.0")))
    meta_llama_api_key: str = Field(default=os.getenv("META_LLAMA_API_KEY", ""))
    
    # Anthropic (Claude) — benchmark reference / final fallback tier (spec §4.3)
    anthropic_enabled: bool = Field(default=os.getenv("ANTHROPIC_ENABLED", "true").lower() == "true")
    anthropic_api_key: str = Field(default=os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = Field(default=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"))

    # Local chat tier (qwen3:8b on the existing Ollama box; spec §4.3-4.4)
    ollama_chat_enabled: bool = Field(default=os.getenv("OLLAMA_CHAT_ENABLED", "true").lower() == "true")
    ollama_chat_model: str = Field(default=os.getenv("OLLAMA_CHAT_MODEL", "qwen3:8b"))
    ollama_chat_timeout: float = Field(default=float(os.getenv("OLLAMA_CHAT_TIMEOUT", "20.0")))

    # Provider chain order (comma-separated; unknown/unconfigured names are skipped)
    llm_provider_order: str = Field(default=os.getenv("LLM_PROVIDER_ORDER", "ollama,openrouter,anthropic"))
    
    # Database settings
    postgres_conn: str = Field(
        default="postgresql://user:password@localhost:5432/ats_db",
        env=["POSTGRES_CONN", "DATABASE_URL"]
    )

    # Embeddings (Ollama over the existing Cloudflare tunnel; spec §4.2)
    ollama_base_url: str = Field(default=os.getenv("OLLAMA_BASE_URL", "https://ollama.sentienttrader.ai"))
    ollama_embed_model: str = Field(default=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"))
    ollama_embed_timeout: float = Field(default=float(os.getenv("OLLAMA_EMBED_TIMEOUT", "20.0")))
    
    # Redis settings
    redis_host: str = Field(default=os.getenv("REDIS_HOST", "localhost"))
    redis_port: int = Field(default=int(os.getenv("REDIS_PORT", "6379")))
    redis_password: Optional[str] = Field(default=os.getenv("REDIS_PASSWORD", None))
    
    # MinIO settings
    minio_endpoint: str = Field(default=os.getenv("MINIO_ENDPOINT", "localhost:9000"))
    minio_access_key: str = Field(default=os.getenv("MINIO_ACCESS_KEY", "minioadmin"))
    minio_secret_key: str = Field(default=os.getenv("MINIO_SECRET_KEY", "minioadmin"))
    
    # Application settings
    api_version: str = Field(default=os.getenv("API_VERSION", "v1"))
    enable_swagger: bool = Field(default=os.getenv("ENABLE_SWAGGER", "true").lower() == "true")
    
    # Resume parser settings
    LLM_VALIDATE_ADDRESSES: bool = Field(default=os.getenv("LLM_VALIDATE_ADDRESSES", "false").lower() == "true")
    # Experience extraction behavior
    # If true, prefer clean, model-native experience data without heuristic merges
    EXPERIENCE_CLEAN_MODE: bool = Field(default=os.getenv("EXPERIENCE_CLEAN_MODE", "true").lower() == "true")
    # If true, disable any resume/person specific heuristics (e.g., special pattern tweaks)
    DISABLE_RESUME_SPECIFIC_HEURISTICS: bool = Field(default=os.getenv("DISABLE_RESUME_SPECIFIC_HEURISTICS", "true").lower() == "true")
    # Optional: allow merging LLM and regex experience when clean mode is off
    ENABLE_EXPERIENCE_FALLBACK_MERGE: bool = Field(default=os.getenv("ENABLE_EXPERIENCE_FALLBACK_MERGE", "false").lower() == "true")
    
    # Intent detection settings
    INTENT_ROUTER_MODE: str = Field(default=os.getenv("INTENT_ROUTER_MODE", "hybrid"))  # semantic|legacy|hybrid
    # Comma-separated list of intents that should prefer the Meta Llama model when generating assistant responses
    ASSISTANT_META_LLAMA_INTENTS: str = Field(default=os.getenv("ASSISTANT_META_LLAMA_INTENTS", ""))
    
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        # `.env` files have lowest priority
        env_file=find_dotenv(),
        env_file_encoding='utf-8',
        extra='ignore'  # Ignore extra fields from .env
    )


# Singleton instance of settings
_settings = None

def get_settings():
    """Return a singleton instance of Settings"""
    global _settings
    if _settings is None:
        env_path = find_dotenv()
        logging.info(f"Loading Settings from .env: '{env_path or 'not found'}'")
        _settings = Settings()
    return _settings
