"""Diagnostic probe for eval zero-scores. Dumps RAW model output + finish_reason
for specific fixtures, so failures can be diagnosed from evidence rather than
inferred from the aggregate score. Not part of the suite; run manually.

    poetry run python evals/probe_failures.py ollama
    poetry run python evals/probe_failures.py openrouter openai/gpt-5-nano p01a
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))

from backend.utils.config import get_settings  # noqa: E402
from backend.utils.resume_parsing.contracts.resume_contract import ResumeV2  # noqa: E402
from backend.utils.resume_parsing.extractors.structured_extractor import (  # noqa: E402
    create_extraction_prompt,
)
from evals.scorer import score_extraction  # noqa: E402

SYSTEM = "You are a resume parsing specialist AI. Extract relevant information accurately."


def _fixture(fid):
    text = (ROOT / "resumes" / f"{fid}.txt").read_text(encoding="utf-8")
    labels = json.loads((ROOT / "labels" / f"{fid}.json").read_text(encoding="utf-8"))
    return text, labels


def _report(fid, raw, labels, extra=""):
    print(f"\n{'=' * 70}\n{fid}{extra}\n{'=' * 70}")
    print(f"raw length: {len(raw)} chars")
    print(f"--- RAW (first 1200) ---\n{raw[:1200]}")
    if len(raw) > 1200:
        print(f"--- RAW (last 300) ---\n{raw[-300:]}")
    try:
        parsed = json.loads(raw)
        print(f"\nstrict json.loads: OK, top-level keys = {list(parsed)[:20]}")
    except Exception as e:
        parsed = None
        print(f"\nstrict json.loads: FAILED ({type(e).__name__}: {e})")
    if parsed is not None:
        scores = score_extraction(parsed, labels)
        print(f"scores: { {k: f'{v:.0%}' for k, v in scores.items()} }")
        print(f"overall: {sum(scores.values()) / len(scores):.0%}")


async def probe_ollama(fixture_ids):
    import httpx

    s = get_settings()
    schema = ResumeV2.model_json_schema()
    for fid in fixture_ids:
        text, labels = _fixture(fid)
        payload = {
            "model": s.ollama_chat_model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": create_extraction_prompt(text, schema)},
            ],
            "stream": False,
            "think": False,
            "options": {"num_predict": 4096},
            "format": schema,
        }
        async with httpx.AsyncClient(timeout=180.0) as c:
            r = await c.post(f"{s.ollama_base_url.rstrip('/')}/api/chat", json=payload)
        body = r.json()
        raw = (body.get("message") or {}).get("content", "")
        meta = (
            f"  [done_reason={body.get('done_reason')} "
            f"eval_count={body.get('eval_count')} "
            f"prompt_eval_count={body.get('prompt_eval_count')}]"
        )
        _report(fid, raw, labels, meta)


async def probe_openrouter(model, fixture_ids):
    import httpx

    s = get_settings()
    schema = ResumeV2.model_json_schema()
    for fid in fixture_ids:
        text, labels = _fixture(fid)
        user = (
            f"{create_extraction_prompt(text, schema)}\n\nReturn ONLY a valid JSON object"
            f" conforming to this JSON schema — no code fences, no explanations:\n{json.dumps(schema)}"
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "max_tokens": 4096,
        }
        from backend.services.llm.openai_compat_provider import OpenAICompatProvider

        url = OpenAICompatProvider(
            name="openrouter",
            base_url=s.openrouter_base_url,
            api_key=s.openrouter_api_key,
            model=model,
        )._url
        async with httpx.AsyncClient(timeout=180.0) as c:
            r = await c.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {s.openrouter_api_key}"},
            )
        body = r.json()
        choice = (body.get("choices") or [{}])[0]
        raw = (choice.get("message") or {}).get("content") or ""
        reasoning = (choice.get("message") or {}).get("reasoning") or ""
        meta = (
            f"  [status={r.status_code} finish_reason={choice.get('finish_reason')}"
            f" native={choice.get('native_finish_reason')} usage={body.get('usage')}"
            f" reasoning_chars={len(reasoning)}]"
        )
        _report(fid, raw, labels, meta)


if __name__ == "__main__":
    which = sys.argv[1]
    if which == "ollama":
        ids = sys.argv[2:] or ["p08a", "p04a", "p01b", "p03c"]
        asyncio.run(probe_ollama(ids))
    else:
        model = sys.argv[2]
        ids = sys.argv[3:] or ["p01a"]
        asyncio.run(probe_openrouter(model, ids))
