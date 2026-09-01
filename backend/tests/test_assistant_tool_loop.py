"""Unit tests for the Phase 2 tool-calling assistant. No network, no LLM."""
import asyncio

import pytest

from backend.services import tool_loop as tl
from backend.services.assistant_tools import Tool, execute_tool
from backend.services.tool_loop import ToolLoopError, run_tool_loop


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _echo(**kwargs):
    return {"echo": kwargs}


async def _boom(**kwargs):
    raise RuntimeError("db exploded")


TOOLS = [
    Tool(name="echo", description="echoes", parameters={"type": "object", "properties": {}}, run=_echo),
    Tool(name="boom", description="raises", parameters={"type": "object", "properties": {}}, run=_boom),
]


class TestExecuteTool:
    def test_runs_tool(self):
        result = run(execute_tool(TOOLS, "echo", {"a": 1}))
        assert result == {"echo": {"a": 1}}

    def test_unknown_tool_returns_error(self):
        result = run(execute_tool(TOOLS, "nope", {}))
        assert "error" in result

    def test_bad_arguments_return_error(self):
        result = run(execute_tool(TOOLS, "echo", {"unexpected": True, "another": 2}))
        # _echo accepts **kwargs so this succeeds; use a strict tool instead
        async def strict(only: str):
            return {"only": only}

        strict_tool = [Tool(name="strict", description="", parameters={}, run=strict)]
        result = run(execute_tool(strict_tool, "strict", {"wrong": "x"}))
        assert "error" in result

    def test_tool_exception_returns_error(self):
        result = run(execute_tool(TOOLS, "boom", {}))
        assert "error" in result and "db exploded" in result["error"]


class _Settings:
    ollama_chat_enabled = True
    ollama_base_url = "https://example.invalid"
    ollama_chat_model = "qwen3:8b"
    ollama_chat_timeout = 20.0
    openrouter_api_key = "sk-test"
    openrouter_enabled = True
    openrouter_base_url = "https://openrouter.ai/api/v1"
    openrouter_default_model = "test-model"
    openrouter_timeout = 60.0
    anthropic_api_key = ""
    anthropic_enabled = True
    anthropic_model = "claude-haiku-4-5"
    llm_provider_order = "ollama,openrouter,anthropic"


class TestEnabledProviders:
    def test_order_and_key_gating(self):
        assert tl._enabled_providers(_Settings()) == ["ollama", "openrouter"]

    def test_anthropic_included_with_key(self):
        s = _Settings()
        s.anthropic_api_key = "sk-ant-test"
        assert tl._enabled_providers(s) == ["ollama", "openrouter", "anthropic"]

    def test_local_can_be_disabled(self):
        s = _Settings()
        s.ollama_chat_enabled = False
        assert tl._enabled_providers(s) == ["openrouter"]


class TestRunToolLoop:
    def _patch_runners(self, monkeypatch, ollama=None, openrouter=None):
        async def default_fail(settings, system, messages, tools, trace):
            raise RuntimeError("down")

        monkeypatch.setitem(tl._RUNNERS, "ollama", ollama or default_fail)
        monkeypatch.setitem(tl._RUNNERS, "openrouter", openrouter or default_fail)

    def test_first_provider_serves(self, monkeypatch):
        async def ok(settings, system, messages, tools, trace):
            assert messages[-1] == {"role": "user", "content": "hi"}
            trace.append({"tool": "echo", "arguments": {}, "ok": True})
            return "hello from local"

        self._patch_runners(monkeypatch, ollama=ok)
        result = run(run_tool_loop(_Settings(), system="sys", message="hi", tools=TOOLS))
        assert result.provider == "ollama"
        assert result.text == "hello from local"
        assert result.tool_trace == [{"tool": "echo", "arguments": {}, "ok": True}]

    def test_falls_through_to_next_provider(self, monkeypatch):
        async def ok(settings, system, messages, tools, trace):
            return "served by cloud"

        self._patch_runners(monkeypatch, openrouter=ok)
        result = run(run_tool_loop(_Settings(), system="sys", message="hi", tools=TOOLS))
        assert result.provider == "openrouter"

    def test_all_fail_raises(self, monkeypatch):
        self._patch_runners(monkeypatch)
        with pytest.raises(ToolLoopError):
            run(run_tool_loop(_Settings(), system="sys", message="hi", tools=TOOLS))

    def test_history_is_forwarded(self, monkeypatch):
        seen = {}

        async def ok(settings, system, messages, tools, trace):
            seen["messages"] = list(messages)
            return "ok"

        self._patch_runners(monkeypatch, ollama=ok)
        history = [
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier answer"},
            {"role": "weird", "content": "dropped"},
            {"role": "user", "content": ""},
        ]
        run(run_tool_loop(_Settings(), system="sys", message="now", history=history, tools=TOOLS))
        assert seen["messages"] == [
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier answer"},
            {"role": "user", "content": "now"},
        ]


class TestAssistantToolSchemas:
    def test_search_candidates_accepts_location(self):
        # Building the tool set only binds closures; nothing touches the db.
        from backend.services.assistant_tools import build_assistant_tools

        tools = {t.name: t for t in build_assistant_tools(None)}
        schema = tools["search_candidates"].parameters
        assert "location" in schema["properties"]
        assert schema["required"] == ["query"], "location must stay optional"


class TestLocationFilterPatterns:
    """Pure pattern expansion for the location filter; no DB involved."""

    def test_region_expands_to_states(self):
        from backend.services.vector_search_service import location_filter_patterns

        patterns = location_filter_patterns("west coast")
        assert "%, CA%" in patterns and "%, WA%" in patterns and "%, OR%" in patterns

    def test_region_is_case_insensitive_and_survives_phrasing(self):
        from backend.services.vector_search_service import location_filter_patterns

        assert location_filter_patterns("West Coast") == location_filter_patterns("west coast")
        assert location_filter_patterns("along the west coast") == location_filter_patterns(
            "west coast"
        )
        assert location_filter_patterns("the Pacific Northwest") == location_filter_patterns("pnw")

    def test_metro_expands_to_cities(self):
        from backend.services.vector_search_service import location_filter_patterns

        assert "%San Francisco%" in location_filter_patterns("bay area")

    def test_plain_place_stays_substring(self):
        from backend.services.vector_search_service import location_filter_patterns

        assert location_filter_patterns("Seattle") == ["%Seattle%"]
        assert location_filter_patterns("Austin, TX") == ["%Austin, TX%"]

    def test_unconstrained_place_means_no_filter(self):
        """"Anywhere" is not a place; empty patterns mean skip the WHERE.
        Small models pass the user's word through even when the schema says
        omit, so the catch has to live in the tool, not the prompt."""
        from backend.services.vector_search_service import location_filter_patterns

        for phrase in (
            "Anywhere", "anywhere", "any location", "anyplace", "everywhere",
            "no preference", "nationwide", "US", "USA", "the US",
            "United States", "anywhere in the US", "anywhere in the world",
        ):
            assert location_filter_patterns(phrase) == [], phrase

    def test_anywhere_in_a_region_still_filters(self):
        from backend.services.vector_search_service import location_filter_patterns

        assert location_filter_patterns("anywhere in the midwest") == location_filter_patterns(
            "midwest"
        )
        assert location_filter_patterns("anywhere in Seattle") == ["%seattle%"]

    def test_remote_is_a_real_filter_not_anywhere(self):
        # Candidate locations are stored as "Remote, US": "remote" must keep
        # filtering, not be swallowed by the unconstrained vocabulary.
        from backend.services.vector_search_service import location_filter_patterns

        assert location_filter_patterns("remote") == ["%remote%"]


class TestCandidateEmbeddingText:
    def test_includes_company_and_headline(self):
        """Industry lives in the headline and employer; position+skills alone
        made every candidate embed like the same tech resume."""
        from types import SimpleNamespace

        from backend.services.vector_search_service import _candidate_text

        candidate = SimpleNamespace(
            current_position="Data Platform Engineer",
            current_company="Allstate",
            headline="Lakehouse migrations at a national insurance carrier",
            skills=[SimpleNamespace(skill_name="Python"), SimpleNamespace(skill_name="Spark")],
        )
        text = _candidate_text(candidate)
        assert "Allstate" in text
        assert "insurance" in text
        assert "Python, Spark" in text


class TestToolSpecs:
    def test_openai_and_anthropic_shapes(self):
        oa = tl._openai_tool_spec(TOOLS)
        assert oa[0]["type"] == "function"
        assert oa[0]["function"]["name"] == "echo"
        an = tl._anthropic_tool_spec(TOOLS)
        assert an[0]["name"] == "echo"
        assert "input_schema" in an[0]


class TestOpenRouterChatUrl:
    """Both base-url forms are in the wild (dev .env carries the suffix, prod
    doesn't). The doubled-suffix 404 silently killed the whole tier."""

    def test_bare_base_gets_suffix(self):
        assert (
            tl._openrouter_chat_url("https://openrouter.ai/api/v1")
            == "https://openrouter.ai/api/v1/chat/completions"
        )

    def test_suffixed_base_is_not_doubled(self):
        assert (
            tl._openrouter_chat_url("https://openrouter.ai/api/v1/chat/completions")
            == "https://openrouter.ai/api/v1/chat/completions"
        )

    def test_trailing_slash_is_stripped(self):
        assert (
            tl._openrouter_chat_url("https://openrouter.ai/api/v1/")
            == "https://openrouter.ai/api/v1/chat/completions"
        )
