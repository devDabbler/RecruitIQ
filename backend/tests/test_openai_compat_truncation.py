"""A truncated completion must not be reported as a successful one.

Regression cover for a bug found by evals 2026-08-27. `_extract_content`
discarded `finish_reason`, so a response cut off at the token limit was returned
as if complete. Downstream the JSON-repair layer turns that fragment into a
partial dict, so the caller silently stores half a resume and the chain never
falls through to a tier that could have answered fully.

This bites hardest with reasoning models: gpt-5-nano spent all 4096 budgeted
tokens on reasoning (`reasoning_tokens == completion_tokens`) and emitted zero
visible characters, yet the call looked like a success.
"""
import asyncio
import json

import httpx
import pytest

from backend.services.llm.base import ProviderError
from backend.services.llm.openai_compat_provider import OpenAICompatProvider


def _provider(**kw):
    kw.setdefault("max_retries", 1)
    return OpenAICompatProvider(
        name="test", base_url="https://example.invalid/api/v1", api_key="k", model="m", **kw
    )


def _response(content, finish_reason="stop", usage=None):
    body = {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5},
    }
    return httpx.Response(
        200, content=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )


def _run_with(monkeypatch, response):
    async def fake_post(self, url, **kwargs):
        return response

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    return asyncio.new_event_loop().run_until_complete(_provider().generate("hi"))


def test_truncated_response_raises_rather_than_returning_a_fragment(monkeypatch):
    partial = '{"personal_info": {"name": "Aisha Al-Rashid", "email": "a@b.c'
    with pytest.raises(ProviderError) as excinfo:
        _run_with(monkeypatch, _response(partial, finish_reason="length"))
    assert "truncated" in str(excinfo.value).lower()


def test_reasoning_model_that_emits_only_reasoning_raises(monkeypatch):
    """Whole budget spent thinking, no visible content: must not look like success."""
    usage = {
        "prompt_tokens": 5851,
        "completion_tokens": 4096,
        "completion_tokens_details": {"reasoning_tokens": 4096},
    }
    with pytest.raises(ProviderError):
        _run_with(monkeypatch, _response("", finish_reason="length", usage=usage))


def test_complete_response_still_succeeds(monkeypatch):
    result = _run_with(monkeypatch, _response('{"ok": true}', finish_reason="stop"))
    assert result.text == '{"ok": true}'


def test_missing_finish_reason_is_not_treated_as_truncation(monkeypatch):
    """Not every OpenAI-compatible vendor returns finish_reason; absence must
    stay permissive or we would break providers that are working fine."""
    result = _run_with(monkeypatch, _response('{"ok": true}', finish_reason=None))
    assert result.text == '{"ok": true}'


def test_usage_is_carried_through_on_success(monkeypatch):
    result = _run_with(monkeypatch, _response('{"ok": true}'))
    assert result.extra["usage"]["prompt_tokens"] == 10
