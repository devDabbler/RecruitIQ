"""The provider chain: try each enabled tier in order, fall through on failure."""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from backend.services.llm.base import AllProvidersFailedError, LLMProvider, LLMResult, SchemaLike

logger = logging.getLogger(__name__)


class ProviderChain:
    def __init__(self, providers: List[LLMProvider]):
        self.providers = providers

    async def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[SchemaLike] = None,
        **kwargs: Any,
    ) -> LLMResult:
        errors: list = []
        for provider in self.providers:
            try:
                result = await provider.generate(
                    prompt,
                    system=system,
                    max_tokens=max_tokens,
                    json_schema=json_schema,
                    **kwargs,
                )
                logger.info(
                    "LLM call served by %s (%s) in %d ms", result.provider, result.model, result.latency_ms
                )
                return result
            except Exception as e:  # noqa: BLE001 - any provider failure falls through
                logger.warning("Provider %s failed: %s", provider.name, e)
                errors.append(e)
        raise AllProvidersFailedError(errors)


def build_chain(settings, order: Optional[str] = None) -> ProviderChain:
    """Assemble the chain from settings: Ollama -> OpenRouter -> Claude.

    Order comes from ``llm_provider_order`` unless ``order`` overrides it (used
    for per-task routing, ADR 0002). Each comma-separated entry is a provider
    name, optionally with a pinned model — ``openrouter:google/gemini-2.5-flash-lite``
    — the same spec vocabulary as ``evals/run_eval.py --providers``, so an eval
    winner can be pasted into config verbatim. Providers missing keys or
    explicitly disabled are skipped.
    """
    from backend.services.llm.anthropic_provider import AnthropicProvider
    from backend.services.llm.ollama_provider import OllamaProvider
    from backend.services.llm.openai_compat_provider import OpenAICompatProvider

    available: dict = {}

    if getattr(settings, "ollama_chat_enabled", True):
        available["ollama"] = lambda model=None: OllamaProvider(
            base_url=getattr(settings, "ollama_base_url", "https://ollama.sentienttrader.ai"),
            model=model or getattr(settings, "ollama_chat_model", "qwen3:8b"),
            timeout=getattr(settings, "ollama_chat_timeout", 20.0),
        )

    openrouter_key = getattr(settings, "openrouter_api_key", "")
    if openrouter_key and getattr(settings, "openrouter_enabled", True):
        available["openrouter"] = lambda model=None: OpenAICompatProvider(
            name="openrouter",
            base_url=getattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1"),
            api_key=openrouter_key,
            model=model or getattr(settings, "openrouter_default_model", "meta-llama/llama-3.3-8b-instruct:free"),
            timeout=getattr(settings, "openrouter_timeout", 60.0),
            max_retries=getattr(settings, "openrouter_max_retries", 2),
        )

    anthropic_key = getattr(settings, "anthropic_api_key", "")
    if anthropic_key and getattr(settings, "anthropic_enabled", True):
        available["anthropic"] = lambda model=None: AnthropicProvider(
            api_key=anthropic_key,
            model=model or getattr(settings, "anthropic_model", "claude-haiku-4-5"),
        )

    specs = [
        p.strip()
        for p in (order or getattr(settings, "llm_provider_order", "ollama,openrouter,anthropic")).split(",")
        if p.strip()
    ]
    providers = []
    for spec in specs:
        # Split on the FIRST colon only: the remainder is the model id, which
        # may itself contain colons ("ollama:qwen3:32b").
        name, _, model = spec.partition(":")
        if name in available:
            providers.append(available[name](model or None))
    logger.info("LLM provider chain: %s", [p.name for p in providers] or "EMPTY")
    return ProviderChain(providers)
