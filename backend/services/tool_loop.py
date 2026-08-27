"""Provider-agnostic agentic tool loop for the assistant.

Runs a chat conversation with native tool calling against the first available
tier of the provider chain (Ollama -> OpenRouter -> Claude). If a tier fails,
the whole conversation is retried on the next tier — tool calls are cheap DB
reads, so re-running them is safe.

Guardrails follow spec §4.4: the local tier gets a hard timeout and no
retries; the loop is capped at MAX_ITERATIONS to bound cost per message.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from backend.services.assistant_tools import Tool, execute_tool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5


@dataclass
class ToolLoopResult:
    text: str
    provider: str
    model: str
    latency_ms: int = 0
    tool_trace: List[dict] = field(default_factory=list)


class ToolLoopError(Exception):
    pass


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
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            result = await execute_tool(tools, name, args)
            trace.append({"tool": name, "arguments": args, "ok": "error" not in result})
            convo.append({"role": "tool", "tool_name": name, "content": _json_dumps(result)})
    raise ToolLoopError("ollama: exceeded max tool iterations")


async def _run_openrouter(settings, system: str, messages: List[dict], tools: List[Tool], trace: list) -> str:
    api_key = getattr(settings, "openrouter_api_key", "")
    base_url = getattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1").rstrip("/")
    model = getattr(settings, "openrouter_default_model", "meta-llama/llama-3.3-8b-instruct:free")
    timeout = getattr(settings, "openrouter_timeout", 60.0)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    convo = [{"role": "system", "content": system}] + list(messages)

    for _ in range(MAX_ITERATIONS):
        payload = {"model": model, "messages": convo, "tools": _openai_tool_spec(tools)}
        async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
            resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
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
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await execute_tool(tools, name, args)
            trace.append({"tool": name, "arguments": args, "ok": "error" not in result})
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
            result = await execute_tool(tools, block.name, dict(block.input or {}))
            trace.append({"tool": block.name, "arguments": dict(block.input or {}), "ok": "error" not in result})
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
) -> ToolLoopResult:
    """Run one assistant turn with tool calling, falling through provider tiers."""
    messages: List[dict] = []
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    providers = _enabled_providers(settings)
    if not providers:
        raise ToolLoopError("No LLM providers configured")

    errors = []
    for name in providers:
        trace: List[dict] = []
        started = time.monotonic()
        try:
            text = await _RUNNERS[name](settings, system, messages, tools, trace)
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
            )
        except Exception as e:  # noqa: BLE001 - fall through to next tier
            logger.warning("Tool loop on %s failed: %s", name, e)
            errors.append(f"{name}: {e}")
    raise ToolLoopError("All providers failed: " + "; ".join(errors))
