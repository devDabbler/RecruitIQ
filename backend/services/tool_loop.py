"""Provider-agnostic agentic tool loop for the assistant.

Runs a chat conversation with native tool calling against the first available
tier of the provider chain (Ollama -> OpenRouter -> Claude). If a tier fails,
the whole conversation is retried on the next tier — tool calls are cheap DB
reads, so re-running them is safe.

Guardrails follow spec §4.4: the local tier gets a hard timeout and no
retries; the loop is capped at MAX_ITERATIONS to bound cost per message, and
the whole turn (every tier, every tool) shares one wall-clock budget.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx

from backend.services.assistant_tools import Tool, execute_tool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5

# One turn's wall-clock budget across all tiers and tools. Measured worst case
# before this existed: 78.8s for one salary answer with the local tier timing
# out five times and OpenRouter then re-running the whole conversation.
# nginx cuts the connection at 300s; the browser gave up never.
DEFAULT_TURN_BUDGET_S = 90.0

# History is replayed into every model call, so an unbounded history is an
# unbounded prompt. The most recent turns are the ones that matter.
MAX_HISTORY_TURNS = 20
MAX_HISTORY_CHARS = 8000

EventSink = Callable[[dict], Awaitable[None]]


@dataclass
class ToolLoopResult:
    text: str
    provider: str
    model: str
    latency_ms: int = 0
    tool_trace: List[dict] = field(default_factory=list)
    # What the serving tier's tools returned, in call order. The answer
    # finalizer links the names in here; the trace itself stays a list of
    # {tool, arguments, ok} so the stream and its consumers are unchanged.
    tool_results: List[Any] = field(default_factory=list)


class ToolLoopError(Exception):
    pass


class ToolLoopTimeout(ToolLoopError):
    """The turn ran out of its wall-clock budget before any tier answered."""


def _parse_tool_args(raw: Any) -> dict:
    """Tool-call arguments as a dict, whatever the provider sent.

    Ollama returns them as a dict, OpenRouter as a JSON string, and a small
    model can emit a string that is not JSON at all. That used to raise out of
    the Ollama runner and fail the whole tier; an empty argument set lets the
    tool return a "bad arguments" error the model can recover from.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Unparseable tool-call arguments: %.200r", raw)
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def trim_history(history: Optional[List[Dict[str, str]]]) -> List[dict]:
    """Normalise and bound the replayed conversation.

    Keeps only user/assistant turns with content, then the most recent
    MAX_HISTORY_TURNS of them, then drops the oldest until the total is under
    MAX_HISTORY_CHARS. The audit sent 100 turns of 1000 characters each and
    the assistant dutifully replayed all of it into every model call.
    """
    turns = [
        {"role": t.get("role"), "content": t.get("content", "")}
        for t in history or []
        if t.get("role") in ("user", "assistant") and t.get("content")
    ]
    turns = turns[-MAX_HISTORY_TURNS:]
    total = sum(len(t["content"]) for t in turns)
    while turns and total > MAX_HISTORY_CHARS:
        total -= len(turns.pop(0)["content"])
    return turns


def _summarize(result: Any) -> str:
    """A short, human-readable description of what a tool came back with.

    This is what the user sees streaming past — "found 12 candidates" — so it
    should read like progress, not like a debug dump.
    """
    if isinstance(result, dict):
        if "error" in result:
            return str(result["error"])[:200]
        for key, value in result.items():
            if isinstance(value, list):
                return f"{len(value)} {key}"
        return ", ".join(list(result)[:4])
    if isinstance(result, list):
        return f"{len(result)} results"
    return str(result)[:200]


class ToolTrace(list):
    """The loop's tool trace, which can also report each call as it happens.

    A plain list of completed calls, exactly as before — `run_tool_loop` already
    collected these and simply threw the timing away. Passing an `on_event` sink
    additionally streams `tool_start`/`tool_end` while the loop runs, which is
    what /chat/stream turns into SSE. Subclassing list keeps every existing
    `trace.append(...)` caller working untouched.
    """

    def __init__(self, on_event: Optional[EventSink] = None):
        super().__init__()
        self._on_event = on_event
        self.results: List[Any] = []

    async def _emit(self, event: dict) -> None:
        if self._on_event is None:
            return
        try:
            await self._on_event(event)
        except Exception:  # noqa: BLE001
            # A consumer that has gone away (browser tab closed) must not take
            # the tool loop down with it.
            logger.debug("Tool event sink raised; continuing", exc_info=True)
        # Hand the event loop to whoever consumes the event before the tool
        # runs. Putting onto an unbounded queue never suspends, and the tools
        # do sync ORM work on the loop, so without this the stream's drain task
        # first ran after the tool returned: tool_start and tool_end reached the
        # browser in the same packet and the visitor never saw "running".
        await asyncio.sleep(0)

    async def tool_started(self, tool: str, arguments: dict) -> None:
        await self._emit({"type": "tool_start", "tool": tool, "arguments": arguments})

    async def tier_retry(self, failed: str, next_tier: str) -> None:
        """The next provider tier re-runs the conversation from the top, so the
        tool calls narrated so far are about to happen again."""
        await self._emit({"type": "tier_retry", "failed": failed, "next": next_tier})

    async def tool_finished(self, tool: str, arguments: dict, result: Any) -> None:
        ok = not (isinstance(result, dict) and "error" in result)
        self.append({"tool": tool, "arguments": arguments, "ok": ok})
        self.results.append(result)
        await self._emit(
            {"type": "tool_end", "tool": tool, "ok": ok, "summary": _summarize(result)}
        )


def _openai_tool_spec(tools: List[Tool]) -> list:
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
        }
        for t in tools
    ]


def _anthropic_tool_spec(tools: List[Tool]) -> list:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.parameters}
        for t in tools
    ]


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _openrouter_chat_url(base_url: str) -> str:
    """OPENROUTER_BASE_URL is configured both with and without the
    /chat/completions suffix (dev .env has it, prod doesn't), and
    OpenAICompatProvider accepts either. Doubling the suffix 404s every call,
    which silently killed this whole tier."""
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


async def _run_ollama(settings, system: str, messages: List[dict], tools: List[Tool], trace: list) -> str:
    base_url = getattr(settings, "ollama_base_url", "https://ollama.sentienttrader.ai").rstrip("/")
    model = getattr(settings, "ollama_chat_model", "qwen3:8b")
    timeout = getattr(settings, "ollama_chat_timeout", 20.0)
    convo = [{"role": "system", "content": system}] + list(messages)

    for _ in range(MAX_ITERATIONS):
        payload = {
            "model": model,
            "messages": convo,
            "stream": False,
            "think": False,
            "tools": _openai_tool_spec(tools),
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{base_url}/api/chat", json=payload)
        resp.raise_for_status()
        msg = resp.json().get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            content = msg.get("content", "")
            if not content:
                raise ToolLoopError("ollama returned empty content")
            return content
        convo.append(msg)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name", "")
            args = _parse_tool_args(fn.get("arguments"))
            await trace.tool_started(name, args)
            result = await execute_tool(tools, name, args)
            await trace.tool_finished(name, args, result)
            convo.append({"role": "tool", "tool_name": name, "content": _json_dumps(result)})
    raise ToolLoopError("ollama: exceeded max tool iterations")


async def _run_openrouter(settings, system: str, messages: List[dict], tools: List[Tool], trace: list) -> str:
    api_key = getattr(settings, "openrouter_api_key", "")
    url = _openrouter_chat_url(getattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1"))
    model = getattr(settings, "openrouter_default_model", "qwen/qwen3.8-27b")
    timeout = getattr(settings, "openrouter_timeout", 60.0)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    convo = [{"role": "system", "content": system}] + list(messages)

    for _ in range(MAX_ITERATIONS):
        payload = {"model": model, "messages": convo, "tools": _openai_tool_spec(tools)}
        async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
            resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        choices = resp.json().get("choices") or []
        if not choices:
            raise ToolLoopError("openrouter returned no choices")
        msg = choices[0].get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            content = msg.get("content", "")
            if not content:
                raise ToolLoopError("openrouter returned empty content")
            return content
        convo.append(msg)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name", "")
            args = _parse_tool_args(fn.get("arguments"))
            await trace.tool_started(name, args)
            result = await execute_tool(tools, name, args)
            await trace.tool_finished(name, args, result)
            convo.append(
                {"role": "tool", "tool_call_id": call.get("id", ""), "content": _json_dumps(result)}
            )
    raise ToolLoopError("openrouter: exceeded max tool iterations")


async def _run_anthropic(settings, system: str, messages: List[dict], tools: List[Tool], trace: list) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=getattr(settings, "anthropic_api_key", ""))
    model = getattr(settings, "anthropic_model", "claude-haiku-4-5")
    convo = list(messages)

    for _ in range(MAX_ITERATIONS):
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            messages=convo,
            tools=_anthropic_tool_spec(tools),
        )
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            text = next((b.text for b in response.content if b.type == "text"), "")
            if not text:
                raise ToolLoopError(f"anthropic returned no text (stop_reason={response.stop_reason})")
            return text
        convo.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            args = dict(block.input or {})
            await trace.tool_started(block.name, args)
            result = await execute_tool(tools, block.name, args)
            await trace.tool_finished(block.name, args, result)
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": _json_dumps(result)}
            )
        convo.append({"role": "user", "content": results})
    raise ToolLoopError("anthropic: exceeded max tool iterations")


_RUNNERS = {
    "ollama": _run_ollama,
    "openrouter": _run_openrouter,
    "anthropic": _run_anthropic,
}


def _enabled_providers(settings) -> List[str]:
    order = [
        p.strip()
        for p in getattr(settings, "llm_provider_order", "ollama,openrouter,anthropic").split(",")
        if p.strip()
    ]
    enabled = []
    for name in order:
        if name == "ollama" and getattr(settings, "ollama_chat_enabled", True):
            enabled.append(name)
        elif name == "openrouter" and getattr(settings, "openrouter_api_key", "") and getattr(
            settings, "openrouter_enabled", True
        ):
            enabled.append(name)
        elif name == "anthropic" and getattr(settings, "anthropic_api_key", "") and getattr(
            settings, "anthropic_enabled", True
        ):
            enabled.append(name)
    return enabled


async def run_tool_loop(
    settings,
    *,
    system: str,
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    tools: List[Tool],
    on_event: Optional[EventSink] = None,
) -> ToolLoopResult:
    """Run one assistant turn with tool calling, falling through provider tiers.

    `on_event`, if given, is awaited with a `tool_start`/`tool_end` dict as each
    tool runs, and with `tier_retry` when a tier fails and the next one is
    about to re-run the conversation (its tool calls included).

    The whole turn shares one wall-clock budget (`settings.assistant_turn_budget_s`,
    default DEFAULT_TURN_BUDGET_S). A tier that outlives what is left is
    cancelled, and the turn fails with ToolLoopTimeout rather than starting
    another tier that cannot finish either.
    """
    messages: List[dict] = trim_history(history)
    messages.append({"role": "user", "content": message})

    providers = _enabled_providers(settings)
    if not providers:
        raise ToolLoopError("No LLM providers configured")

    budget = float(getattr(settings, "assistant_turn_budget_s", DEFAULT_TURN_BUDGET_S))
    turn_started = time.monotonic()

    errors = []
    for index, name in enumerate(providers):
        remaining = budget - (time.monotonic() - turn_started)
        if remaining <= 0:
            raise ToolLoopTimeout(
                f"Turn budget of {budget:.0f}s exhausted before {name} could run; " + "; ".join(errors)
            )
        trace = ToolTrace(on_event)
        started = time.monotonic()
        try:
            text = await asyncio.wait_for(
                _RUNNERS[name](settings, system, messages, tools, trace), timeout=remaining
            )
            model = {
                "ollama": getattr(settings, "ollama_chat_model", "qwen3:8b"),
                "openrouter": getattr(settings, "openrouter_default_model", ""),
                "anthropic": getattr(settings, "anthropic_model", "claude-haiku-4-5"),
            }[name]
            return ToolLoopResult(
                text=text,
                provider=name,
                model=model,
                latency_ms=int((time.monotonic() - started) * 1000),
                tool_trace=trace,
                tool_results=trace.results,
            )
        except asyncio.TimeoutError as e:
            # On 3.11+ asyncio.TimeoutError is the builtin TimeoutError, which a
            # runner could raise for its own reasons; only the budget counts.
            if time.monotonic() - turn_started >= budget - 0.05:
                logger.warning("Tool loop on %s hit the %.0fs turn budget", name, budget)
                raise ToolLoopTimeout(
                    f"Turn budget of {budget:.0f}s exhausted on {name}; " + "; ".join(errors)
                ) from None
            logger.warning("Tool loop on %s failed: %s", name, e)
            errors.append(f"{name}: {e}")
            if index + 1 < len(providers):
                await trace.tier_retry(name, providers[index + 1])
        except Exception as e:  # noqa: BLE001 - fall through to next tier
            logger.warning("Tool loop on %s failed: %s", name, e)
            errors.append(f"{name}: {e}")
            if index + 1 < len(providers):
                await trace.tier_retry(name, providers[index + 1])
    raise ToolLoopError("All providers failed: " + "; ".join(errors))
