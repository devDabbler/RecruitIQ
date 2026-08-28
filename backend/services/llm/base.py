"""Common types for the LLM provider chain."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional, Type, Union

from pydantic import BaseModel

# A structured-output request: either a raw JSON schema dict or a Pydantic model class.
SchemaLike = Union[dict, Type[BaseModel]]


def schema_to_dict(schema: SchemaLike) -> dict:
    """Normalize a SchemaLike to a plain JSON schema dict."""
    if isinstance(schema, dict):
        return schema
    return schema.model_json_schema()


@dataclass
class LLMResult:
    """Result of one successful provider call."""

    text: str
    provider: str
    model: str
    latency_ms: int = 0
    # For structured calls: parsed dict when the provider guarantees/validated
    # conformance itself; None means the caller must parse `text`.
    data: Optional[dict] = None
    extra: dict = field(default_factory=dict)

    def parsed(self) -> dict:
        """Return structured data, parsing `text` as JSON if needed."""
        if self.data is not None:
            return self.data
        return json.loads(self.text)


class ProviderError(Exception):
    """A single provider failed (timeout, HTTP error, bad payload)."""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(f"{provider}: {message}")


class AllProvidersFailedError(Exception):
    """Every provider in the chain failed for this request."""

    def __init__(self, errors: list):
        self.errors = errors
        detail = "; ".join(str(e) for e in errors) or "no providers configured"
        super().__init__(f"All LLM providers failed: {detail}")


class LLMProvider:
    """Interface each provider implements."""

    name: str = "base"
    model: str = ""

    async def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[SchemaLike] = None,
        **kwargs: Any,
    ) -> LLMResult:
        raise NotImplementedError
