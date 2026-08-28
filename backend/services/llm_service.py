"""LLM service facade.

Phase 2 replaced the old per-provider spaghetti (Nebius/Cohere/Gemini/Meta
Llama) with a single provider chain: Ollama (local, best-effort) ->
OpenRouter -> Claude. This module keeps the public interface that ~40 call
sites depend on (``get_llm_service``, ``generate_text_async``,
``generate_text``, ``generate_content``, ``get_embedding_model``) and
delegates the actual calls to :mod:`backend.services.llm`.
"""
import logging
from typing import Any, Dict, Optional

from backend.services.llm.base import AllProvidersFailedError, SchemaLike
from backend.services.llm.chain import ProviderChain, build_chain
from backend.utils.config import Settings, get_settings

logger = logging.getLogger(__name__)

_FALLBACK_MESSAGE = (
    "I'm having trouble generating a response with my AI service right now. Please try again later."
)


class LLMService:
    """Facade over the provider chain, preserving the legacy interface."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.embedding_model = None
        self._embedding_model_loaded = False
        self._chain: Optional[ProviderChain] = None
        self._task_chains: Dict[str, ProviderChain] = {}

    @property
    def chain(self) -> ProviderChain:
        if self._chain is None:
            self._chain = build_chain(self.settings)
        return self._chain

    def chain_for(self, task_type: str) -> ProviderChain:
        """The chain for this task type (ADR 0002 per-task routing).

        A task is routed iff settings define ``llm_provider_order_<task_type>``
        (e.g. resume_parsing -> the eval winner); every other task_type shares
        the default local-first chain.
        """
        order = getattr(self.settings, f"llm_provider_order_{task_type}", "") or None
        if order is None:
            return self.chain
        if order not in self._task_chains:
            self._task_chains[order] = build_chain(self.settings, order=order)
        return self._task_chains[order]

    def get_embedding_model(self):
        """Return the shared 768-dim Ollama embedding adapter (loaded once)."""
        if not self._embedding_model_loaded:
            from backend.services.ollama_embeddings import OllamaEmbeddingAdapter

            self.embedding_model = OllamaEmbeddingAdapter(
                base_url=getattr(self.settings, "ollama_base_url", "https://ollama.sentienttrader.ai"),
                model=getattr(self.settings, "ollama_embed_model", "nomic-embed-text"),
                timeout=getattr(self.settings, "ollama_embed_timeout", 20.0),
            )
            self._embedding_model_loaded = True
        return self.embedding_model

    async def generate_text_async(
        self,
        prompt: str,
        model=None,
        task_type: str = "chat",
        system_message: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text via the provider chain.

        ``model`` is honored as an override only by providers that accept it
        (OpenRouter slug or Claude model id); the local tier always runs its
        configured model.
        """
        try:
            result = await self.chain_for(task_type).generate(
                prompt,
                system=system_message,
                max_tokens=max_tokens,
                model=model if isinstance(model, str) else None,
            )
            return result.text
        except AllProvidersFailedError as e:
            logger.error("LLM generation failed for task_type=%s: %s", task_type, e)
            return _FALLBACK_MESSAGE

    async def generate_text(
        self,
        prompt: str,
        model_type=None,
        task_type: str = "general",
        max_tokens: Optional[int] = None,
        system_message: Optional[str] = None,
    ) -> str:
        """Legacy signature; ``model_type`` is ignored."""
        return await self.generate_text_async(
            prompt, task_type=task_type, system_message=system_message, max_tokens=max_tokens
        )

    async def generate_content(self, prompt: str, **kwargs: Any) -> str:
        """Alias kept for compatibility."""
        return await self.generate_text_async(prompt=prompt, **kwargs)

    async def generate_structured(
        self,
        prompt: str,
        schema: SchemaLike,
        *,
        system_message: Optional[str] = None,
        max_tokens: Optional[int] = None,
        task_type: str = "structured",
    ) -> Dict[str, Any]:
        """Generate a dict conforming to ``schema`` (Pydantic model or JSON schema).

        Providers with native schema support (Ollama format param, Claude
        ``messages.parse``) enforce it server-side; for OpenAI-compatible
        providers the caller-facing JSON-repair layer handles drift.

        Raises AllProvidersFailedError when every tier fails — structured
        callers need to know, unlike chat callers who get a fallback string.
        """
        result = await self.chain_for(task_type).generate(
            prompt,
            system=system_message,
            max_tokens=max_tokens,
            json_schema=schema,
        )
        if result.data is not None:
            return result.data
        try:
            return result.parsed()
        except Exception:
            from backend.services.improved_json_handling import extract_json_from_llm_response

            logger.info("Structured output from %s needed JSON repair", result.provider)
            return extract_json_from_llm_response(result.text)


def get_llm_service(settings: Optional[Settings] = None) -> LLMService:
    """Factory kept for the existing import sites."""
    if settings is None:
        settings = get_settings()
    return LLMService(settings)
