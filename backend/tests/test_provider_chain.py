"""Unit tests for the Phase 2 LLM provider chain. No network calls."""
import asyncio

import pytest
from pydantic import BaseModel

from backend.services.llm.base import AllProvidersFailedError, LLMProvider, LLMResult, ProviderError, schema_to_dict
from backend.services.llm.chain import ProviderChain, build_chain


class FakeProvider(LLMProvider):
    def __init__(self, name, *, text="ok", fail=False, data=None):
        self.name = name
        self.model = f"{name}-model"
        self.fail = fail
        self.text = text
        self.data = data
        self.calls = 0

    async def generate(self, prompt, *, system=None, max_tokens=None, json_schema=None, **kwargs):
        self.calls += 1
        if self.fail:
            raise ProviderError(self.name, "boom")
        return LLMResult(text=self.text, provider=self.name, model=self.model, data=self.data)


class ToySchema(BaseModel):
    name: str


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestProviderChain:
    def test_first_provider_wins(self):
        first = FakeProvider("first")
        second = FakeProvider("second")
        chain = ProviderChain([first, second])
        result = run(chain.generate("hi"))
        assert result.provider == "first"
        assert second.calls == 0

    def test_falls_through_on_failure(self):
        first = FakeProvider("first", fail=True)
        second = FakeProvider("second", text="from-second")
        chain = ProviderChain([first, second])
        result = run(chain.generate("hi"))
        assert result.provider == "second"
        assert result.text == "from-second"
        assert first.calls == 1

    def test_all_fail_raises(self):
        chain = ProviderChain([FakeProvider("a", fail=True), FakeProvider("b", fail=True)])
        with pytest.raises(AllProvidersFailedError):
            run(chain.generate("hi"))

    def test_empty_chain_raises(self):
        with pytest.raises(AllProvidersFailedError):
            run(ProviderChain([]).generate("hi"))

    def test_structured_result_parsed(self):
        provider = FakeProvider("p", text='{"name": "Ada"}')
        chain = ProviderChain([provider])
        result = run(chain.generate("hi", json_schema=ToySchema))
        assert result.parsed() == {"name": "Ada"}

    def test_structured_result_prefers_data(self):
        provider = FakeProvider("p", text="irrelevant", data={"name": "Grace"})
        chain = ProviderChain([provider])
        result = run(chain.generate("hi", json_schema=ToySchema))
        assert result.parsed() == {"name": "Grace"}


class TestSchemaToDict:
    def test_dict_passthrough(self):
        schema = {"type": "object"}
        assert schema_to_dict(schema) is schema

    def test_pydantic_model(self):
        schema = schema_to_dict(ToySchema)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]


class _Settings:
    """Minimal settings stub for build_chain."""

    ollama_chat_enabled = True
    ollama_base_url = "https://example.invalid"
    ollama_chat_model = "qwen3:8b"
    ollama_chat_timeout = 20.0
    openrouter_api_key = "sk-test"
    openrouter_enabled = True
    openrouter_base_url = "https://openrouter.ai/api/v1"
    openrouter_default_model = "meta-llama/llama-3.3-8b-instruct:free"
    openrouter_timeout = 60.0
    openrouter_max_retries = 2
    anthropic_api_key = "sk-ant-test"
    anthropic_enabled = True
    anthropic_model = "claude-haiku-4-5"
    llm_provider_order = "ollama,openrouter,anthropic"


class TestBuildChain:
    def test_full_chain_order(self):
        chain = build_chain(_Settings())
        assert [p.name for p in chain.providers] == ["ollama", "openrouter", "anthropic"]

    def test_missing_keys_skip_providers(self):
        settings = _Settings()
        settings.openrouter_api_key = ""
        settings.anthropic_api_key = ""
        chain = build_chain(settings)
        assert [p.name for p in chain.providers] == ["ollama"]

    def test_order_override(self):
        settings = _Settings()
        settings.llm_provider_order = "anthropic,ollama"
        chain = build_chain(settings)
        assert [p.name for p in chain.providers] == ["anthropic", "ollama"]

    def test_ollama_guardrails(self):
        chain = build_chain(_Settings())
        ollama = chain.providers[0]
        assert ollama.timeout == 20.0  # spec §4.4: hard cap, never block the GPU


class TestTaskRouting:
    """Per-task chain orders (ADR 0002): `provider:model` specs, same vocabulary
    as evals/run_eval.py --providers."""

    def test_order_spec_with_model_override(self):
        settings = _Settings()
        chain = build_chain(settings, order="openrouter:google/gemini-2.5-flash-lite,ollama")
        assert [p.name for p in chain.providers] == ["openrouter", "ollama"]
        assert chain.providers[0].model == "google/gemini-2.5-flash-lite"

    def test_ollama_model_spec_survives_colons(self):
        chain = build_chain(_Settings(), order="ollama:qwen3:32b")
        assert chain.providers[0].model == "qwen3:32b"

    def test_spec_without_model_keeps_configured_default(self):
        chain = build_chain(_Settings(), order="openrouter")
        assert chain.providers[0].model == _Settings.openrouter_default_model

    def test_resume_parsing_routes_to_eval_winner(self):
        from backend.services.llm_service import LLMService

        settings = _Settings()
        settings.llm_provider_order_resume_parsing = (
            "openrouter:google/gemini-2.5-flash-lite,anthropic,ollama"
        )
        service = LLMService(settings=settings)
        chain = service.chain_for("resume_parsing")
        assert [p.name for p in chain.providers] == ["openrouter", "anthropic", "ollama"]
        assert chain.providers[0].model == "google/gemini-2.5-flash-lite"

    def test_unrouted_task_uses_default_chain(self):
        from backend.services.llm_service import LLMService

        service = LLMService(settings=_Settings())
        assert service.chain_for("chat") is service.chain

    def test_routed_chain_is_cached(self):
        from backend.services.llm_service import LLMService

        settings = _Settings()
        settings.llm_provider_order_resume_parsing = "anthropic,ollama"
        service = LLMService(settings=settings)
        assert service.chain_for("resume_parsing") is service.chain_for("resume_parsing")


class TestLLMServiceFacade:
    def test_generate_text_async_returns_fallback_when_all_fail(self):
        from backend.services.llm_service import LLMService

        service = LLMService(settings=_Settings())
        service._chain = ProviderChain([FakeProvider("a", fail=True)])
        text = run(service.generate_text_async("hello"))
        assert "trouble" in text.lower()

    def test_generate_structured_raises_when_all_fail(self):
        from backend.services.llm_service import LLMService

        service = LLMService(settings=_Settings())
        service._chain = ProviderChain([FakeProvider("a", fail=True)])
        with pytest.raises(AllProvidersFailedError):
            run(service.generate_structured("hello", ToySchema))

    def test_generate_structured_repairs_sloppy_json(self):
        from backend.services.llm_service import LLMService

        service = LLMService(settings=_Settings())
        sloppy = 'Here is your JSON:\n```json\n{"name": "Lin"}\n```'
        service._chain = ProviderChain([FakeProvider("a", text=sloppy)])
        data = run(service.generate_structured("hello", ToySchema))
        assert data == {"name": "Lin"}
