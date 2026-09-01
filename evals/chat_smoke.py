"""One-off assistant tool-loop comparison: current tiers vs qwen3.8-27b.

Runs the production system prompt and real assistant tools against the dev DB,
once per (model, question). Not CI; run manually:

    poetry run python evals/chat_smoke.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.routers.assistant import SYSTEM_PROMPT  # noqa: E402
from backend.services.assistant_tools import build_assistant_tools  # noqa: E402
from backend.services.tool_loop import run_tool_loop  # noqa: E402
from backend.utils.config import get_settings  # noqa: E402
from backend.utils.database import SessionLocal  # noqa: E402


class _Override:
    """settings proxy: attribute overrides on top of the real settings."""

    def __init__(self, base, **overrides):
        self._base = base
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._base, name)


QUESTIONS = [
    "How many candidates do we have in the pipeline right now, and what stages are they in?",
    "Find me Python engineers on the west coast and rank them.",
    "Who is our strongest candidate for the Data Engineer role, and why?",
]

CONFIGS = [
    ("local (tier 1)", {"llm_provider_order": "ollama"}),
    ("openrouter default (tier 2)", {"llm_provider_order": "openrouter"}),
    # To benchmark a candidate, add a config pinning it:
    # ("candidate", {"llm_provider_order": "openrouter",
    #                "openrouter_default_model": "vendor/model-id"}),
]


async def main():
    base = get_settings()
    for label, overrides in CONFIGS:
        settings = _Override(base, **overrides)
        print(f"\n{'=' * 70}\n=== {label}\n{'=' * 70}")
        for q in QUESTIONS:
            db = SessionLocal()
            try:
                started = time.monotonic()
                try:
                    result = await run_tool_loop(
                        settings,
                        system=SYSTEM_PROMPT,
                        message=q,
                        tools=build_assistant_tools(db),
                    )
                except Exception as e:
                    print(f"\nQ: {q}\n  FAILED in {time.monotonic() - started:.1f}s: {type(e).__name__}: {e}")
                    continue
                tools_used = [t["tool"] for t in result.tool_trace]
                print(f"\nQ: {q}")
                print(f"  {result.latency_ms} ms, tools={tools_used}, model={result.model}")
                text = result.text.strip().replace("\n", "\n  | ")
                print(f"  | {text[:1200]}")
            finally:
                db.close()


if __name__ == "__main__":
    asyncio.run(main())
