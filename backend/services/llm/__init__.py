"""Provider chain for LLM calls: Ollama (local) -> OpenRouter -> Claude.

Spec: docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md §4.3-4.5
"""
from backend.services.llm.base import AllProvidersFailedError, LLMProvider, LLMResult
from backend.services.llm.chain import ProviderChain, build_chain

__all__ = [
    "AllProvidersFailedError",
    "LLMProvider",
    "LLMResult",
    "ProviderChain",
    "build_chain",
]
