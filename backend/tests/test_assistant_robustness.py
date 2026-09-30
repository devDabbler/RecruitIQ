"""The assistant stays responsive and polite when things go slowly or wrong.

Regression net for the 2026-09-30 assistant audit (F3, F4, F6, F7): tool
narration that reaches the browser while the tool is still running, a
wall-clock budget per turn, visitor-safe error copy, and bounded inputs.
Nothing here needs Postgres or a model.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from backend.routers import assistant as assistant_router
from backend.services import tool_loop as tl
from backend.services.assistant_tools import MAX_TOOL_LIMIT, Tool, clamp_limit, execute_tool
from backend.services.tool_loop import (
    MAX_HISTORY_CHARS,
    MAX_HISTORY_TURNS,
    ToolLoopError,
    ToolLoopTimeout,
    ToolTrace,
    run_tool_loop,
    trim_history,
)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _Settings:
    ollama_chat_enabled = True
    ollama_chat_model = "qwen3:8b"
    openrouter_api_key = "sk-test"
    openrouter_enabled = True
    openrouter_default_model = "test-model"
    anthropic_api_key = ""
    anthropic_enabled = False
    llm_provider_order = "ollama,openrouter"
    assistant_turn_budget_s = 90.0


# --- F3: narration reaches the consumer before the tool runs ---------------


class TestToolStartReachesTheStreamFirst:
    def test_consumer_sees_tool_start_while_a_blocking_tool_is_still_running(self):
        """The stream endpoint drains a queue from its own task. A tool that
        does sync work on the event loop used to finish before that task ever
        ran, so tool_start and tool_end left the server in the same packet."""

        async def blocking_tool(**kwargs):
            time.sleep(0.2)  # sync ORM work on the loop, like the real tools
            return {"candidates": [1]}

        tools = [Tool(name="slow", description="", parameters={}, run=blocking_tool)]

        async def scenario():
            queue: asyncio.Queue = asyncio.Queue()
            received = {}

            async def sink(event):
                await queue.put(event)

            async def drain():
                while True:
                    event = await queue.get()
                    received[event["type"]] = time.monotonic()
                    if event["type"] == "tool_end":
                        return

            drainer = asyncio.create_task(drain())
            trace = ToolTrace(sink)
            await trace.tool_started("slow", {})
            result = await execute_tool(tools, "slow", {})
            await trace.tool_finished("slow", {}, result)
            await drainer
            return received

        received = run(scenario())
        assert received["tool_end"] - received["tool_start"] >= 0.15


# --- F4: one wall-clock budget per turn ------------------------------------


class TestTurnBudget:
    def _settings(self, budget: float) -> _Settings:
        s = _Settings()
        s.assistant_turn_budget_s = budget
        return s

    def test_a_tier_that_outlives_the_budget_is_cut_off(self, monkeypatch):
        async def forever(settings, system, messages, tools, trace):
            await asyncio.sleep(5)
            return "too late"

        async def never(settings, system, messages, tools, trace):
            raise AssertionError("no tier may start after the budget is gone")

        monkeypatch.setitem(tl._RUNNERS, "ollama", forever)
        monkeypatch.setitem(tl._RUNNERS, "openrouter", never)

        started = time.monotonic()
        with pytest.raises(ToolLoopTimeout):
            run(run_tool_loop(self._settings(0.2), system="s", message="hi", tools=[]))
        assert time.monotonic() - started < 2

    def test_timeout_is_a_tool_loop_error_so_existing_handlers_catch_it(self):
        assert issubclass(ToolLoopTimeout, ToolLoopError)

    def test_a_fast_tier_is_unaffected(self, monkeypatch):
        async def quick(settings, system, messages, tools, trace):
            return "done"

        monkeypatch.setitem(tl._RUNNERS, "ollama", quick)
        result = run(run_tool_loop(self._settings(0.5), system="s", message="hi", tools=[]))
        assert result.text == "done"

    def test_a_provider_timeout_that_is_not_the_budget_falls_through(self, monkeypatch):
        """httpx and friends can raise TimeoutError for their own reasons; that
        is a tier failure, not the turn's budget, and the next tier still runs."""

        async def flaky(settings, system, messages, tools, trace):
            raise asyncio.TimeoutError("read timed out")

        async def cloud(settings, system, messages, tools, trace):
            return "served by cloud"

        monkeypatch.setitem(tl._RUNNERS, "ollama", flaky)
        monkeypatch.setitem(tl._RUNNERS, "openrouter", cloud)
        result = run(run_tool_loop(self._settings(30), system="s", message="hi", tools=[]))
        assert result.provider == "openrouter"

    def test_falling_through_announces_a_tier_retry(self, monkeypatch):
        """The next tier re-runs every tool call, so the UI must reset its list
        instead of showing each call twice."""
        events = []

        async def sink(event):
            events.append(event)

        async def local(settings, system, messages, tools, trace):
            await trace.tool_started("search_candidates", {})
            await trace.tool_finished("search_candidates", {}, {"candidates": []})
            raise RuntimeError("ollama returned empty content")

        async def cloud(settings, system, messages, tools, trace):
            await trace.tool_started("search_candidates", {})
            await trace.tool_finished("search_candidates", {}, {"candidates": [1]})
            return "one person"

        monkeypatch.setitem(tl._RUNNERS, "ollama", local)
        monkeypatch.setitem(tl._RUNNERS, "openrouter", cloud)
        result = run(
            run_tool_loop(self._settings(30), system="s", message="hi", tools=[], on_event=sink)
        )
        assert [e["type"] for e in events] == [
            "tool_start", "tool_end", "tier_retry", "tool_start", "tool_end",
        ]
        assert events[2] == {"type": "tier_retry", "failed": "ollama", "next": "openrouter"}
        assert result.provider == "openrouter"
        assert len(result.tool_trace) == 1, "only the serving tier's calls are the trace"

    def test_the_last_tier_failing_announces_nothing(self, monkeypatch):
        events = []

        async def sink(event):
            events.append(event)

        async def down(settings, system, messages, tools, trace):
            raise RuntimeError("down")

        monkeypatch.setitem(tl._RUNNERS, "ollama", down)
        monkeypatch.setitem(tl._RUNNERS, "openrouter", down)
        with pytest.raises(ToolLoopError):
            run(run_tool_loop(self._settings(30), system="s", message="hi", tools=[], on_event=sink))
        assert [e["type"] for e in events] == ["tier_retry"]


# --- F7: bounded inputs ----------------------------------------------------


class TestHistoryTrim:
    def test_keeps_only_the_most_recent_turns(self):
        history = [{"role": "user", "content": f"turn {i}"} for i in range(100)]
        trimmed = trim_history(history)
        assert len(trimmed) == MAX_HISTORY_TURNS
        assert trimmed[-1]["content"] == "turn 99"
        assert trimmed[0]["content"] == f"turn {100 - MAX_HISTORY_TURNS}"

    def test_drops_oldest_until_under_the_character_cap(self):
        history = [{"role": "assistant", "content": "x" * 1000} for _ in range(20)]
        history[-1] = {"role": "user", "content": "the latest question"}
        trimmed = trim_history(history)
        assert sum(len(t["content"]) for t in trimmed) <= MAX_HISTORY_CHARS
        assert trimmed[-1]["content"] == "the latest question"

    def test_drops_turns_with_no_content_or_unknown_roles(self):
        trimmed = trim_history(
            [
                {"role": "system", "content": "ignore me"},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "kept"},
                {"role": "user", "content": "kept too"},
            ]
        )
        assert trimmed == [
            {"role": "assistant", "content": "kept"},
            {"role": "user", "content": "kept too"},
        ]

    def test_the_loop_replays_the_trimmed_history(self, monkeypatch):
        seen = {}

        async def ok(settings, system, messages, tools, trace):
            seen["messages"] = list(messages)
            return "ok"

        monkeypatch.setitem(tl._RUNNERS, "ollama", ok)
        history = [{"role": "user", "content": "q"}] * 100
        run(run_tool_loop(_Settings(), system="s", message="now", history=history, tools=[]))
        assert len(seen["messages"]) == MAX_HISTORY_TURNS + 1
        assert seen["messages"][-1] == {"role": "user", "content": "now"}


class TestClampLimit:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (100000, MAX_TOOL_LIMIT),
            (0, 1),
            (-5, 1),
            (7, 7),
            ("12", 12),
            ("lots", 8),
            (None, 8),
            (3.9, 3),
        ],
    )
    def test_forces_the_model_choice_into_range(self, value, expected):
        assert clamp_limit(value, default=8) == expected

    def test_search_and_match_tools_clamp_their_limit(self):
        """The wiring, not the arithmetic: both tools must actually call it.
        Reading the closures is not possible, so this inspects the source."""
        import inspect

        from backend.services import assistant_tools

        source = inspect.getsource(assistant_tools.build_assistant_tools)
        assert "limit = clamp_limit(limit, default=8)" in source
        assert "_rank_for_job(job, clamp_limit(limit, default=10))" in source


class TestToolArgumentParsing:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ({"query": "x"}, {"query": "x"}),
            ('{"query": "x"}', {"query": "x"}),
            ("", {}),
            (None, {}),
            ("not json at all", {}),
            ("[1, 2]", {}),
        ],
    )
    def test_never_raises(self, raw, expected):
        assert tl._parse_tool_args(raw) == expected


# --- F6: what the visitor sees when a turn fails ---------------------------


class TestFailureReplies:
    def test_each_failure_kind_has_visitor_safe_copy(self):
        replies = {
            assistant_router._failure_reply(ToolLoopTimeout("budget")),
            assistant_router._failure_reply(ToolLoopError("all down")),
            assistant_router._failure_reply(RuntimeError("relation candidates does not exist")),
        }
        assert replies == {
            assistant_router.TIMEOUT_REPLY,
            assistant_router.PROVIDERS_DOWN_REPLY,
            assistant_router.UNEXPECTED_ERROR_REPLY,
        }
        for reply in replies:
            assert "—" not in reply and "–" not in reply

    def test_chat_turns_an_unexpected_exception_into_a_sentence(self, demo_client, monkeypatch):
        async def explode(settings, **kwargs):
            raise RuntimeError("relation candidates does not exist")

        monkeypatch.setattr(assistant_router, "run_tool_loop", explode)
        response = demo_client.post("/api/assistant/chat", json={"message": "hi"})
        assert response.status_code == 200
        assert response.json()["response"] == assistant_router.UNEXPECTED_ERROR_REPLY
        assert "relation" not in response.text

    def test_chat_reports_a_timeout_as_a_timeout(self, demo_client, monkeypatch):
        async def slow(settings, **kwargs):
            raise ToolLoopTimeout("Turn budget of 90s exhausted on ollama")

        monkeypatch.setattr(assistant_router, "run_tool_loop", slow)
        response = demo_client.post("/api/assistant/chat", json={"message": "hi"})
        assert response.json()["response"] == assistant_router.TIMEOUT_REPLY

    def test_stream_never_sends_the_exception_text(self, demo_client, monkeypatch):
        async def explode(settings, **kwargs):
            raise RuntimeError("relation candidates does not exist")

        monkeypatch.setattr(assistant_router, "run_tool_loop", explode)
        response = demo_client.post("/api/assistant/chat/stream", json={"message": "hi"})
        assert response.status_code == 200
        assert "event: error" in response.text
        assert assistant_router.UNEXPECTED_ERROR_REPLY in response.text
        assert "relation" not in response.text

    def test_stream_forwards_tier_retry(self, demo_client, monkeypatch):
        from backend.services.tool_loop import ToolLoopResult

        async def fake_loop(settings, *, on_event=None, **kwargs):
            await on_event({"type": "tool_start", "tool": "get_job", "arguments": {}})
            await on_event({"type": "tier_retry", "failed": "ollama", "next": "openrouter"})
            await on_event({"type": "tool_start", "tool": "get_job", "arguments": {}})
            await on_event({"type": "tool_end", "tool": "get_job", "ok": True, "summary": "ok"})
            return ToolLoopResult(text="answer", provider="openrouter", model="m")

        monkeypatch.setattr(assistant_router, "run_tool_loop", fake_loop)
        response = demo_client.post("/api/assistant/chat/stream", json={"message": "hi"})
        names = [
            line[len("event: "):]
            for line in response.text.splitlines()
            if line.startswith("event: ")
        ]
        assert names == ["tool_start", "tier_retry", "tool_start", "tool_end", "message"]
