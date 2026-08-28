"""Run the parsing eval: regex baseline vs each LLM tier on the fixture set.

This is the decision-making tool from spec §7 — it picks per-task provider
routing empirically. Not run in CI (live LLM calls); run manually:

    poetry run python evals/run_eval.py --providers regex,ollama
    poetry run python evals/run_eval.py --providers "openrouter:google/gemini-2.5-flash-lite"

A provider spec is either a tier name (`regex`, `ollama`, `openrouter`,
`anthropic`) or `openrouter:<model-id>` to benchmark one specific candidate.

Cost is measured from the token counts the API actually reports, priced against
OpenRouter's live catalog — not estimated from assumed prompt sizes.

Writes evals/results.md and evals/results.json.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))

from evals.scorer import ALL_FIELDS, aggregate, score_extraction  # noqa: E402

# The eval measures the production prompt (structured_extractor.create_extraction_prompt),
# so results transfer 1:1 to the live parsing path.


LOW_SCORE_DUMP_THRESHOLD = 0.5

# `time.monotonic()` is QueryPerformanceCounter on Windows and keeps counting while
# the machine is suspended, so a laptop sleeping mid-run silently inflates a latency
# by the length of the nap (observed 2026-08-27: a 2.7s call recorded as 3832s, which
# dragged that tier's mean latency to 130s). Ask Windows not to sleep during the run,
# and report median latency alongside the mean so one artifact can't move the headline.
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _inhibit_sleep():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except Exception as e:
        print(f"  (could not inhibit sleep: {type(e).__name__}: {e})")


def _release_sleep_inhibit():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


def _median(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _dump_failure(label, fixture_id, raw, route, extracted, scores):
    out_dir = ROOT / "failures"
    out_dir.mkdir(exist_ok=True)
    safe = label.replace("/", "_").replace(":", "_")
    body = [
        f"provider: {label}",
        f"fixture:  {fixture_id}",
        f"route:    {route}",
        f"raw length: {len(raw)} chars",
        f"scores:   {json.dumps({k: round(v, 3) for k, v in scores.items()})}",
        "",
        "--- extracted (what the scorer saw) ---",
        json.dumps(extracted, indent=2, default=str)[:4000],
        "",
        "--- raw model response ---",
        raw,
    ]
    (out_dir / f"{safe}-{fixture_id}.txt").write_text("\n".join(body), encoding="utf-8")


def _load_fixtures(limit=None):
    fixtures = []
    for resume_path in sorted((ROOT / "resumes").glob("*.txt")):
        label_path = ROOT / "labels" / f"{resume_path.stem}.json"
        fixtures.append(
            {
                "id": resume_path.stem,
                "text": resume_path.read_text(encoding="utf-8"),
                "labels": json.loads(label_path.read_text(encoding="utf-8")),
            }
        )
    return fixtures[:limit] if limit else fixtures


def _fetch_openrouter_pricing(api_key: str) -> dict:
    """model id -> (usd_per_input_token, usd_per_output_token) from the live catalog."""
    try:
        import httpx

        resp = httpx.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return {
            m["id"]: (float(m["pricing"]["prompt"]), float(m["pricing"]["completion"]))
            for m in resp.json().get("data", [])
            if m.get("pricing")
        }
    except Exception as e:  # pricing is a nice-to-have; never fail the eval over it
        print(f"  (could not fetch OpenRouter pricing: {type(e).__name__}: {e})")
        return {}


async def _extract_regex(text: str):
    from backend.utils.resume_parsing.extractors.regex_extractor import RegexExtractor

    return await RegexExtractor().extract(text, ""), {}, "", "regex"


def _make_llm_extractor(provider):
    from backend.utils.resume_parsing.extractors.structured_extractor import (
        EXTRACTION_MAX_TOKENS,
        ExtractionContract,
        create_extraction_prompt,
        extraction_schema,
    )

    async def extract(text: str):
        result = await provider.generate(
            create_extraction_prompt(text, extraction_schema()),
            system="You are a resume parsing specialist AI. Extract relevant information accurately.",
            max_tokens=EXTRACTION_MAX_TOKENS,
            json_schema=ExtractionContract,
        )
        usage = (result.extra or {}).get("usage") or {}
        # `route` records which parse path produced the data, so a low score can be
        # attributed to the model vs. the repair layer without re-running.
        if result.data is not None:
            return result.data, usage, result.text, "provider_data"
        try:
            return result.parsed(), usage, result.text, "strict_json"
        except Exception as e:
            from backend.services.improved_json_handling import extract_json_from_llm_response

            repaired = extract_json_from_llm_response(result.text)
            return repaired, usage, result.text, f"repaired (strict failed: {type(e).__name__}: {e})"

    return extract


def _build_extractors(specs):
    """Map provider specs to (column_label -> (extract_fn, model_id_or_None))."""
    from backend.utils.config import get_settings

    settings = get_settings()
    extractors = {}
    for spec in specs:
        name, _, model_override = spec.partition(":")
        model_override = model_override or None

        if name == "regex":
            extractors["regex"] = (_extract_regex, None)
        elif name == "ollama":
            from backend.services.llm.ollama_provider import OllamaProvider

            model = model_override or settings.ollama_chat_model
            provider = OllamaProvider(
                base_url=settings.ollama_base_url,
                model=model,
                timeout=120.0,  # eval is offline; allow slow generations rather than skew accuracy
            )
            label = "ollama" if not model_override else f"ollama:{model.split('/')[-1]}"
            extractors[label] = (_make_llm_extractor(provider), model)
        elif name == "openrouter":
            from backend.services.llm.openai_compat_provider import OpenAICompatProvider

            if not settings.openrouter_api_key:
                print("SKIP openrouter: no OPENROUTER_API_KEY")
                continue
            model = model_override or settings.openrouter_default_model
            provider = OpenAICompatProvider(
                name="openrouter",
                base_url=settings.openrouter_base_url,
                api_key=settings.openrouter_api_key,
                model=model,
                timeout=120.0,
                max_retries=4,  # candidates include rate-limited free tiers
            )
            label = model.split("/")[-1] if model_override else "openrouter"
            extractors[label] = (_make_llm_extractor(provider), model)
        elif name == "anthropic":
            from backend.services.llm.anthropic_provider import AnthropicProvider

            if not settings.anthropic_api_key:
                print("SKIP anthropic: no ANTHROPIC_API_KEY")
                continue
            model = model_override or settings.anthropic_model
            provider = AnthropicProvider(api_key=settings.anthropic_api_key, model=model)
            extractors["anthropic"] = (_make_llm_extractor(provider), model)
        else:
            print(f"SKIP unknown provider spec: {spec}")
    return extractors


async def run(specs, limit=None):
    from backend.utils.config import get_settings

    fixtures = _load_fixtures(limit)
    extractors = _build_extractors(specs)
    pricing = {}
    if any(not s.startswith(("regex", "ollama")) for s in specs):
        pricing = _fetch_openrouter_pricing(get_settings().openrouter_api_key)

    results = {}
    for label, (extract, model_id) in extractors.items():
        per_fixture = []
        latencies = []
        failures = 0
        in_tokens = out_tokens = 0
        print(f"\n=== {label} ({len(fixtures)} fixtures) ===")
        for fx in fixtures:
            started = time.monotonic()
            raw, route = "", "n/a"
            try:
                extracted, usage, raw, route = await extract(fx["text"])
            except Exception as e:
                print(f"  {fx['id']}: FAILED ({type(e).__name__}: {e})")
                extracted, usage = {}, {}
                route = f"exception: {type(e).__name__}: {e}"
                failures += 1
            latencies.append(time.monotonic() - started)
            in_tokens += int(usage.get("prompt_tokens") or 0)
            out_tokens += int(usage.get("completion_tokens") or 0)
            scores = score_extraction(extracted or {}, fx["labels"])
            per_fixture.append(scores)
            overall = sum(scores.values()) / len(scores)
            note = ""
            # A near-zero score is almost never a model that "got it wrong" — it means
            # the document never reached the scorer. Persist the raw response so the
            # cause is diagnosable after the fact instead of needing a re-run.
            if overall < LOW_SCORE_DUMP_THRESHOLD:
                note = f"  <- dumped ({route})"
                _dump_failure(label, fx["id"], raw, route, extracted, scores)
            print(f"  {fx['id']}: {overall:.0%} in {latencies[-1]:.1f}s{note}")

        in_price, out_price = pricing.get(model_id, (0.0, 0.0))
        cost = in_tokens * in_price + out_tokens * out_price
        agg = aggregate(per_fixture)
        results[label] = {
            "model": model_id,
            "fields": agg,
            "overall": sum(agg.values()) / len(agg),
            "mean_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
            "median_latency_s": _median(latencies),
            "latencies_s": [round(x, 2) for x in latencies],
            "failures": failures,
            "fixtures": len(fixtures),
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "cost_usd_run": round(cost, 4),
            "cost_usd_per_1k_resumes": round(cost / len(fixtures) * 1000, 2) if fixtures else 0.0,
        }
        r = results[label]
        print(f"  -> overall {r['overall']:.0%}, {r['failures']} failures, ${r['cost_usd_run']:.4f}")
    return results


def write_report(results: dict):
    (ROOT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    providers = list(results.keys())
    lines = [
        "# Resume Parsing Eval Results",
        "",
        f"{next(iter(results.values()))['fixtures']} synthetic fixtures (10 personas x 3 layouts), "
        "field-level accuracy against hand-written labels. Generated by `evals/run_eval.py`.",
        "",
        "| Field | " + " | ".join(providers) + " |",
        "|" + "---|" * (len(providers) + 1),
    ]
    for field in ALL_FIELDS:
        row = [field] + [f"{results[p]['fields'][field]:.0%}" for p in providers]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("| **overall** | " + " | ".join(f"**{results[p]['overall']:.0%}**" for p in providers) + " |")
    lines.append(
        "| median latency | " + " | ".join(f"{results[p]['median_latency_s']:.1f}s" for p in providers) + " |"
    )
    lines.append("| failures | " + " | ".join(str(results[p]["failures"]) for p in providers) + " |")
    lines.append(
        "| $/1k resumes | " + " | ".join(f"${results[p]['cost_usd_per_1k_resumes']:.2f}" for p in providers) + " |"
    )
    lines.append("")
    lines.append("Models: " + ", ".join(f"`{p}` = {results[p]['model'] or 'n/a'}" for p in providers))
    (ROOT / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nWrote evals/results.md and evals/results.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--providers",
        default="regex,ollama,openrouter,anthropic",
        help="comma-separated tier names, or openrouter:<model-id> to pin a candidate",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    _inhibit_sleep()
    try:
        results = asyncio.run(run([p.strip() for p in args.providers.split(",")], args.limit))
    finally:
        _release_sleep_inhibit()
    if results:
        write_report(results)
