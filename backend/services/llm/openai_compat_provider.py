"""OpenAI-compatible cloud tier. One class covers OpenRouter, Groq, Together,
etc. via a base-URL swap (spec §4.3).

Schema conformance is NOT guaranteed by these providers (spec §4.5), so
structured calls get a JSON instruction appended and callers run the
JSON-repair layer on the result.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Optional

import httpx

from backend.services.llm.base import LLMProvider, LLMResult, ProviderError, SchemaLike, schema_to_dict

logger = logging.getLogger(__name__)


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 2,
        backoff_factor: float = 0.8,
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    @property
    def _url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

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
        use_model = model or self.model
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        user_content = prompt
        if json_schema is not None:
            schema = schema_to_dict(json_schema)
            user_content = (
                f"{prompt}\n\nReturn ONLY a valid JSON object conforming to this JSON schema"
                f" — no code fences, no explanations:\n{json.dumps(schema)}"
            )
        messages.append({"role": "user", "content": user_content})

        payload: dict = {"model": use_model, "messages": messages}
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        started = time.monotonic()
        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, trust_env=True) as client:
                    resp = await client.post(self._url, json=payload, headers=headers)
            except httpx.HTTPError as e:
                last_error = f"{type(e).__name__}: {e}"
            else:
                if resp.status_code in (200, 201):
                    content = self._extract_content(resp)
                    if content:
                        return LLMResult(
                            text=content,
                            provider=self.name,
                            model=use_model,
                            latency_ms=int((time.monotonic() - started) * 1000),
                        )
                    last_error = "empty response"
                elif resp.status_code in (401, 403):
                    raise ProviderError(self.name, f"auth failed ({resp.status_code}) — check API key")
                elif 400 <= resp.status_code < 500:
                    raise ProviderError(self.name, f"HTTP {resp.status_code}: {resp.text[:300]}")
                else:
                    last_error = f"HTTP {resp.status_code}"
            if attempt < self.max_retries:
                delay = self.backoff_factor * (2 ** (attempt - 1)) + random.random() * 0.1
                logger.info("%s retry %d/%d in %.1fs (%s)", self.name, attempt, self.max_retries, delay, last_error)
                await asyncio.sleep(delay)

        raise ProviderError(self.name, last_error or "unknown failure")

    @staticmethod
    def _extract_content(resp: httpx.Response) -> str:
        try:
            data = resp.json()
        except json.JSONDecodeError:
            return resp.text
        choices = data.get("choices") or []
        if choices:
            choice = choices[0]
            message = choice.get("message") or {}
            return message.get("content") or choice.get("text") or ""
        return ""
