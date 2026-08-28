# ADR 0002: Per-task LLM routing, chosen by eval

**Date:** 2026-08-27 · **Status:** Accepted (Phase 2c)

## Context

ADR 0001 made the chain order configuration so routing could be decided from
eval results rather than assertion. The eval (spec §7) is 30 synthetic resumes
with hand-written labels, scored field-by-field, sending exactly what
production sends — the same prompt (`create_extraction_prompt`), the same
schema (`ExtractionContract`), the same token budget (`EXTRACTION_MAX_TOKENS`).

Definitive run (`evals/results.md`, 2026-08-27):

| | overall | median latency | $/1k resumes |
|---|---|---|---|
| regex baseline | 49% | 0.03s | $0 |
| `qwen3:8b` (local) | 86% | 6.5s | $0 |
| **`google/gemini-2.5-flash-lite`** | **99%** | **2.6s** | **$0.83** |
| `openai/gpt-5-nano` | 100% | 25.6s | $1.89 |
| `qwen/qwen3-32b` | 95% | 31.8s | $0.81 |

gpt-5-nano is the accuracy winner but spends most of its budget (and wall
clock) on reasoning tokens — 10× gemini's latency at 2.3× the cost. An
earlier run scored it 53%; that number was an artifact of a provider bug that
reported truncated completions as successes, not a measurement. qwen3-32b is
accurate but its latency is erratic (18s–185s on identical work). The local
tier's 86% is dragged down by skills extraction (F1 0.36); it stays excellent
for latency-tolerant chat.

## Decision

Routing is per task type: `llm_provider_order_<task_type>` overrides the
default chain, and an entry may pin a model (`openrouter:<model-id>` — the
same spec syntax as `evals/run_eval.py --providers`, so an eval winner is
pasted into config verbatim).

- **Resume parsing** (low-volume, schema-critical):
  `openrouter:google/gemini-2.5-flash-lite,anthropic,ollama` — best
  accuracy-per-second wins; Claude as schema-guaranteed fallback; local as the
  $0 floor.
- **Chat and everything else** (higher-volume, forgiving): unchanged
  local-first `ollama,openrouter,anthropic` per ADR 0001.

## Consequences

- A parsed resume is stored permanently, so the 13-point accuracy gap over
  local justifies leaving the $0 tier — at $0.83 per thousand resumes.
- Routing changes are config edits backed by a published benchmark; the next
  model debate is settled by `run_eval.py`, not opinion.
- Building the eval paid beyond routing: it surfaced four production bugs
  (truncated completions reported as success, the JSON-repair layer mangling
  already-valid JSON, the model being asked to echo `raw_text` back, and a
  delisted default OpenRouter model failing every call).
