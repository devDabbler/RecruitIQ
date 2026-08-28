"""The streaming assistant: tool-loop events and the SSE endpoint (spec §5).

No network and no model. The tool loop's providers are faked, so what is under
test is the event plumbing — that a tool call is reported when it starts rather
than when the whole turn ends, which is the entire reason the endpoint exists.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from backend.routers import assistant as assistant_router
from backend.services import tool_loop as tl
from backend.services.assistant_tools import Tool
from backend.services.tool_loop import ToolLoopError, ToolLoopResult, run_tool_loop


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _find_candidates(**kwargs):
    return {"candidates": [{"name": "Ada"}, {"name": "Grace"}]}


async def _explode(**kwargs):
    raise RuntimeError("db exploded")


TOOLS = [
    Tool(
        name="search_candidates",
        description="finds candidates",
        parameters={"type": "object", "properties": {}},
        run=_find_candidates,
    ),
    Tool(
        name="broken_tool",
        description="always fails",
        parameters={"type": "object", "properties": {}},
        run=_explode,
    ),
]


class _Settings:
    ollama_chat_enabled = True
    ollama_chat_model = "qwen3:8b"
    openrouter_api_key = ""
    openrouter_enabled = False
    anthropic_api_key = ""
    anthropic_enabled = False
    llm_provider_order = "ollama"


def _runner_calling(tool_name: str):
    """A fake provider that calls one tool and then answers."""

    async def runner(settings, system, messages, tools, trace):
        await trace.tool_started(tool_name, {"query": "engineers"})
        from backend.services.assistant_tools import execute_tool

        result = await execute_tool(tools, tool_name, {})
        await trace.tool_finished(tool_name, {"query": "engineers"}, result)
        return "Here are two engineers."

    return runner


# --- the event sink --------------------------------------------------------


class TestToolTrace:
    def test_events_are_emitted_around_each_tool_call(self, monkeypatch):
        events = []

        async def sink(event):
            events.append(event)

        monkeypatch.setitem(tl._RUNNERS, "ollama", _runner_calling("search_candidates"))
        result = run(
            run_tool_loop(
                _Settings(), system="s", message="who", tools=TOOLS, on_event=sink
            )
        )

        assert [e["type"] for e in events] == ["tool_start", "tool_end"]
        assert events[0]["tool"] == "search_candidates"
        assert events[0]["arguments"] == {"query": "engineers"}
        assert events[1]["ok"] is True
        assert events[1]["summary"] == "2 candidates"
        assert result.text == "Here are two engineers."

    def test_a_failing_tool_is_reported_as_not_ok(self, monkeypatch):
        events = []

        async def sink(event):
            events.append(event)

        monkeypatch.setitem(tl._RUNNERS, "ollama", _runner_calling("broken_tool"))
        run(run_tool_loop(_Settings(), system="s", message="who", tools=TOOLS, on_event=sink))

        assert events[-1]["type"] == "tool_end"
        assert events[-1]["ok"] is False
        assert "db exploded" in events[-1]["summary"]

    def test_the_trace_is_still_a_plain_list_of_completed_calls(self, monkeypatch):
        """/chat reads result.tool_trace; the sink must not change that shape."""
        monkeypatch.setitem(tl._RUNNERS, "ollama", _runner_calling("search_candidates"))
        result = run(run_tool_loop(_Settings(), system="s", message="who", tools=TOOLS))
        assert result.tool_trace == [
            {"tool": "search_candidates", "arguments": {"query": "engineers"}, "ok": True}
        ]

    def test_a_sink_that_raises_does_not_break_the_turn(self, monkeypatch):
        """A closed browser tab must not take the assistant down with it."""

        async def hostile(event):
            raise ConnectionResetError("client went away")

        monkeypatch.setitem(tl._RUNNERS, "ollama", _runner_calling("search_candidates"))
        result = run(
            run_tool_loop(
                _Settings(), system="s", message="who", tools=TOOLS, on_event=hostile
            )
        )
        assert result.text == "Here are two engineers."


class TestSummarize:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ({"candidates": [1, 2, 3]}, "3 candidates"),
            ({"error": "nope"}, "nope"),
            ([1, 2], "2 results"),
            ({"a": 1, "b": 2}, "a, b"),
        ],
    )
    def test_reads_like_progress(self, value, expected):
        assert tl._summarize(value) == expected


# --- the SSE endpoint ------------------------------------------------------


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        events.append((name, data))
    return events


class TestStreamEndpoint:
    def test_tool_activity_arrives_before_the_answer(self, demo_client, monkeypatch):
        async def fake_loop(settings, *, system, message, history, tools, on_event=None):
            await on_event({"type": "tool_start", "tool": "search_candidates", "arguments": {}})
            await on_event(
                {"type": "tool_end", "tool": "search_candidates", "ok": True, "summary": "12 candidates"}
            )
            return ToolLoopResult(
                text="Twelve people match.",
                provider="ollama",
                model="qwen3:8b",
                tool_trace=[{"tool": "search_candidates", "arguments": {}, "ok": True}],
            )

        monkeypatch.setattr(assistant_router, "run_tool_loop", fake_loop)

        response = demo_client.post(
            "/api/assistant/chat/stream", json={"message": "find me engineers"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        # Without this nginx buffers the whole stream and the feature is invisible.
        assert response.headers["x-accel-buffering"] == "no"

        events = _parse_sse(response.text)
        assert [name for name, _ in events] == ["tool_start", "tool_end", "message"]
        assert events[1][1]["summary"] == "12 candidates"
        assert events[2][1]["response"] == "Twelve people match."
        assert events[2][1]["conversation_context"]["last_provider"] == "ollama"

    def test_provider_failure_becomes_an_error_event(self, demo_client, monkeypatch):
        async def fake_loop(settings, **kwargs):
            raise ToolLoopError("all providers down")

        monkeypatch.setattr(assistant_router, "run_tool_loop", fake_loop)

        response = demo_client.post("/api/assistant/chat/stream", json={"message": "hello"})
        events = _parse_sse(response.text)
        assert [name for name, _ in events] == ["error"]
        assert "trouble reaching" in events[0][1]["detail"]

    @pytest.mark.parametrize(
        ("message", "fragment"),
        [("", "need a question"), ("x" * 2001, "too long")],
        ids=["empty", "over-length"],
    )
    def test_input_guards_answer_without_calling_a_model(
        self, demo_client, monkeypatch, message, fragment
    ):
        async def never(*args, **kwargs):
            raise AssertionError("the model should not have been called")

        monkeypatch.setattr(assistant_router, "run_tool_loop", never)

        response = demo_client.post("/api/assistant/chat/stream", json={"message": message})
        events = _parse_sse(response.text)
        assert [name for name, _ in events] == ["message"]
        assert fragment in events[0][1]["response"]

    def test_the_demo_role_may_use_the_stream(self, demo_client, monkeypatch):
        """It is a POST, but it mutates nothing — the gate must let it through."""

        async def fake_loop(settings, **kwargs):
            return ToolLoopResult(text="hi", provider="ollama", model="qwen3:8b")

        monkeypatch.setattr(assistant_router, "run_tool_loop", fake_loop)
        response = demo_client.post("/api/assistant/chat/stream", json={"message": "hi"})
        assert response.status_code == 200


class TestChatContractUnchanged:
    def test_chat_still_returns_response_and_context(self, demo_client, monkeypatch):
        """Phase 2's synchronous contract survives the new endpoint intact."""

        async def fake_loop(settings, **kwargs):
            assert "on_event" not in kwargs or kwargs["on_event"] is None
            return ToolLoopResult(
                text="synchronous answer",
                provider="ollama",
                model="qwen3:8b",
                tool_trace=[{"tool": "get_pipeline_stats", "arguments": {}, "ok": True}],
            )

        monkeypatch.setattr(assistant_router, "run_tool_loop", fake_loop)

        response = demo_client.post("/api/assistant/chat", json={"message": "stats?"})
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"response", "conversation_context"}
        assert body["response"] == "synchronous answer"
        assert body["conversation_context"]["last_tools_used"] == ["get_pipeline_stats"]
