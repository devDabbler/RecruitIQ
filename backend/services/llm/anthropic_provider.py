"""Claude tier — benchmark reference and final fallback (spec §4.3).

Uses the official anthropic SDK. Structured calls go through
``messages.parse`` when given a Pydantic model (guaranteed conformance,
validated client-side) or ``output_config.format`` when given a raw schema.
"""
from __future__ import annotations

import inspect
import logging
import time
from typing import Any, Optional

from pydantic import BaseModel

from backend.services.llm.base import LLMProvider, LLMResult, ProviderError, SchemaLike

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5", timeout: float = 60.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self.api_key, timeout=self.timeout)
        return self._client

    async def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[SchemaLike] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResult:
        import anthropic

        client = self._get_client()
        use_model = model or self.model
        request: dict = {
            "model": use_model,
            "max_tokens": max_tokens or 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            request["system"] = system

        started = time.monotonic()
        try:
            if json_schema is not None and inspect.isclass(json_schema) and issubclass(json_schema, BaseModel):
                response = await client.messages.parse(output_format=json_schema, **request)
                parsed = response.parsed_output
                data = parsed.model_dump(mode="json") if isinstance(parsed, BaseModel) else dict(parsed)
                text = next((b.text for b in response.content if b.type == "text"), "")
                return LLMResult(
                    text=text,
                    provider=self.name,
                    model=use_model,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    data=data,
                )
            if json_schema is not None:
                request["output_config"] = {"format": {"type": "json_schema", "schema": json_schema}}
            response = await client.messages.create(**request)
        except anthropic.APIError as e:
            raise ProviderError(self.name, f"{type(e).__name__}: {e}") from e

        text = next((b.text for b in response.content if b.type == "text"), "")
        if not text:
            raise ProviderError(self.name, f"no text in response (stop_reason={response.stop_reason})")
        return LLMResult(
            text=text,
            provider=self.name,
            model=use_model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
