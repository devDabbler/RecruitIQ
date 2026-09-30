"""Live assistant eval: the golden questions against the real model tiers.

Runs the production system prompt and the real assistant tools against the
database in POSTGRES_CONN, once per (tier, question), and holds every answer
to the checks in evals/assistant_checks.py: no dashes, profile links only to
ids a tool returned, the expected tools, and honest wording where data is
missing. CI replays the same questions with a stub provider
(backend/tests/test_assistant_golden.py); this is the manual run that also
catches a model picking the wrong tool or inventing a person.

    poetry run python evals/chat_smoke.py                 # every tier, every case
    poetry run python evals/chat_smoke.py --tier local    # one tier
    poetry run python evals/chat_smoke.py --case unknown-job --verbose

Exit status is 1 when any case fails, so it can gate a model change.
"""
import argparse
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
from evals.assistant_golden import (  # noqa: E402
    cast_text,
    check_case,
    discover_cast,
    load_cases,
    outcome_of,
    recording_tools,
)


class _Override:
    """settings proxy: attribute overrides on top of the real settings."""

    def __init__(self, base, **overrides):
        self._base = base
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._base, name)


TIERS = {
    "local": {"llm_provider_order": "ollama"},
    "openrouter": {"llm_provider_order": "openrouter"},
    # To benchmark a candidate model, add a tier pinning it:
    # "candidate": {"llm_provider_order": "openrouter",
    #               "openrouter_default_model": "vendor/model-id"},
}


async def run_case(settings, case, cast, verbose):
    db = SessionLocal()
    results = []
    started = time.monotonic()
    try:
        question = cast_text(case.question, cast)
        try:
            result = await run_tool_loop(
                settings,
                system=SYSTEM_PROMPT,
                message=question,
                tools=recording_tools(build_assistant_tools(db), results),
            )
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {case.id:<20} {time.monotonic() - started:5.1f}s  {type(e).__name__}: {e}")
            return False
        tools_used = [t["tool"] for t in result.tool_trace]
        failures = check_case(case, result.text, results, tools_used, cast)
        status = "ok  " if not failures else "FAIL"
        print(
            f"  {status} {case.id:<20} {result.latency_ms / 1000:5.1f}s  "
            f"tools={tools_used} outcome={outcome_of(results)} model={result.model}"
        )
        for failure in failures:
            print(f"       - {failure}")
        if verbose or failures:
            text = result.text.strip().replace("\n", "\n       | ")
            print(f"       | {text[:1200]}")
        return not failures
    finally:
        db.close()


async def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tier", choices=sorted(TIERS), action="append", help="tier(s) to run; default all")
    parser.add_argument("--case", action="append", help="case id(s) to run; default all")
    parser.add_argument("--verbose", action="store_true", help="print every answer, not only failures")
    args = parser.parse_args(argv)

    cases = load_cases()
    if args.case:
        unknown = set(args.case) - {c.id for c in cases}
        if unknown:
            parser.error(f"unknown case(s): {sorted(unknown)}")
        cases = [c for c in cases if c.id in args.case]

    db = SessionLocal()
    try:
        cast = discover_cast(db)
    finally:
        db.close()
    print(f"cast: candidate={cast['candidate']!r} job={cast['job']!r}")

    base = get_settings()
    all_ok = True
    for tier in args.tier or sorted(TIERS):
        settings = _Override(base, **TIERS[tier])
        print(f"\n=== {tier}")
        for case in cases:
            ok = await run_case(settings, case, cast, args.verbose)
            all_ok = all_ok and ok
    print("\nall passed" if all_ok else "\nFAILURES above")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
