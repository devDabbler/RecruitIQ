"""Local Ollama tier (qwen3:8b over the existing Cloudflare tunnel).

Guardrails (spec §4.4): the GPU also serves SentientTrader, so this tier is
best-effort only — a hard timeout, no retries, fall through to cloud on any
failure.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from backend.services.llm.base import LLMProvider, LLMResult, ProviderError, SchemaLike, schema_to_dict

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str = "qwen3:8b", timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[SchemaLike] = None,
        **kwargs: Any,
    ) -> LLMResult:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # qwen3 emits <think> blocks by default; we want plain answers.
            "think": False,
        }
        if max_tokens:
            payload["options"] = {"num_predict": int(max_tokens)}
        if json_schema is not None:
            # Ollama >= 0.5 enforces a JSON schema via the format parameter.
            payload["format"] = schema_to_dict(json_schema)

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.TimeoutException as e:
            raise ProviderError(self.name, f"timed out after {self.timeout}s") from e
        except httpx.HTTPError as e:
            raise ProviderError(self.name, str(e)) from e

        body = resp.json()
        content = (body.get("message") or {}).get("content", "")
        if not content:
            raise ProviderError(self.name, "empty response")

        return LLMResult(
            text=content,
            provider=self.name,
            model=self.model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
