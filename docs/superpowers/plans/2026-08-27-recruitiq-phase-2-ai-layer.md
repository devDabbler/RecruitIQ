# RecruitIQ Phase 2 — AI Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dead/dated AI plumbing with a three-tier provider chain (Ollama → OpenRouter → Claude), replace the 4,338-line regex intent processor with ~8 LLM tool definitions, and build the eval harness that picks per-task provider routing empirically.

**Architecture:** One new `backend/services/llm/` package holds the provider chain behind the *existing* `LLMService` public interface (`generate_text_async`, `generate_structured`, `get_embedding_model`), so the ~40 import sites keep working. A new tool-calling assistant replaces `intent_processor.py` + most of `routers/assistant.py`. A pytest-run eval harness scores regex vs qwen3:8b vs OpenRouter vs Claude Haiku 4.5 on ~30 synthetic labeled resumes and publishes the comparison table.

**Tech Stack:** FastAPI, httpx (Ollama + OpenRouter, OpenAI-compatible), `anthropic` SDK (Claude), Pydantic v2 (`ResumeV2` contract), pytest.

**Spec reference:** `docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md` §4.3–4.6, §7.

**Model IDs (verified current 2026-08-27):** `claude-haiku-4-5` ($1/$5 per MTok), `claude-sonnet-4-6` ($3/$15). Local: `qwen3:8b` via `https://ollama.sentienttrader.ai`. OpenRouter: `meta-llama/llama-3.3-8b-instruct:free` default.

**Credentials:** `OPENROUTER_API_KEY` already in `.env`. `ANTHROPIC_API_KEY` must be added by Sean (blocker only for Claude-tier tests + eval column 4).

---

## Stage A — Provider chain + structured outputs (branch `phase-2a-provider-chain`, one PR)

### Task A1: New provider package

**Files:**
- Create: `backend/services/llm/__init__.py`
- Create: `backend/services/llm/base.py` — `LLMProvider` protocol: `async generate(prompt, *, system, max_tokens, json_schema=None) -> LLMResult`; `LLMResult` dataclass: `text`, `provider`, `model`, `latency_ms`, `schema_conformant: bool | None`
- Create: `backend/services/llm/ollama_provider.py` — `POST {OLLAMA_BASE_URL}/api/chat` with `format: <json_schema>` when schema given (Ollama ≥0.5 schema conformance), hard 20 s timeout, **never retries** (spec §4.4 guard #1)
- Create: `backend/services/llm/openai_compat_provider.py` — one class covers OpenRouter (and any base-URL-swap provider, spec §4.3); JSON mode via `response_format` when supported, JSON-repair (`improved_json_handling.extract_json_from_llm_response`) scoped here (spec §4.5)
- Create: `backend/services/llm/anthropic_provider.py` — official `anthropic` SDK, `AsyncAnthropic`; plain `messages.create` for text, `messages.parse(output_format=<pydantic model>)` for structured; default model `claude-haiku-4-5`
- Create: `backend/services/llm/chain.py` — `ProviderChain.generate()`: iterate enabled providers in order Ollama → OpenRouter → Claude; per-provider try/except with logging; raise `AllProvidersFailedError` at the end
- Tests: `backend/tests/test_provider_chain.py` — fake providers (no network): fallback order, 20 s Ollama cap honored, schema path returns validated dict, all-fail raises

### Task A2: Config + dependencies

**Files:**
- Modify: `backend/utils/config.py` — add `anthropic_api_key`, `anthropic_model` (default `claude-haiku-4-5`), `anthropic_enabled`, `ollama_chat_model` (default `qwen3:8b`), `ollama_chat_timeout` (default `20.0`), `llm_provider_order` (default `"ollama,openrouter,anthropic"`)
- Modify: `.env.example` — document the new keys; mark Nebius section REMOVED
- Modify: `pyproject.toml` — add `anthropic`; remove `cohere`, `google-generativeai` (both disabled per spec)

### Task A3: Route `LLMService` through the chain, delete Nebius

**Files:**
- Modify: `backend/services/llm_service.py` — `generate_text`/`generate_text_async`/`generate_structured_output` delegate to `ProviderChain`; delete `DirectNebiusAI` class and `_initialize_nebius_ai`/`_initialize_cohere`/Gemini/Meta-Llama stubs; keep `get_embedding_model()` untouched (pgvector search depends on it)
- Delete: `backend/services/nebius_ai_service.py`, `backend/services/local_model_service.py`, `backend/services/ollama_service.py` (dead), Nebius-specific tests under `backend/utils/resume_parsing/tests/` (`test_direct_nebius.py`, `test_nebius_exclusive.py`, `test_nebius_integration.py`), `tests/test_resume_parsing_nebius_integration.py`
- Modify: `backend/utils/resume_parsing/resume_parser_main.py` — replace hardcoded `NebiusAIParser` with the chain-backed structured extractor
- Modify: `backend/utils/resume_parsing/extractors/structured_extractor.py` — pass `json_schema=ResumeV2.model_json_schema()` into the chain; keep regex/NLP fallback enhancers
- Verify: warm-start regression gone (the dead-Nebius connection test dies with the class); matching endpoint still returns identical top match

### Task A4: Live smoke + CI

- Manual: `tools/llm_smoke_test.py` against real Ollama tunnel and OpenRouter; Claude tier once key exists
- CI: tests run with all providers mocked (no keys in CI)

## Stage B — Tool calling replaces intent processor (branch `phase-2b-tool-calling`, one PR)

### Task B1: Tool definitions + implementations

**Files:**
- Create: `backend/services/assistant_tools.py` — the 8 tools from spec §4.6 as (JSON schema, async impl) pairs pulling from existing services/queries mapped in the subsystem survey:
  `search_candidates(role?, skills?, location?)`, `get_candidate(id)`, `get_job(id_or_title)`, `match_to_job(job_id)` (agent-framework matching path), `explain_match(job_id, candidate_id)`, `get_market_data(role, location)` (`MarketResearchService.get_comprehensive_salary_benchmark`), `list_pipeline()` (status/skill/location breakdown queries), `parse_resume(file_ref)`
- Tests: `backend/tests/test_assistant_tools.py` — each tool against the dev DB fixtures: known-good shapes, empty-result behavior

### Task B2: Tool-loop chat endpoint

**Files:**
- Create: `backend/services/tool_loop.py` — provider-agnostic agentic loop: OpenAI-format tools for Ollama/OpenRouter (`/api/chat` tools param, `tool_calls` in reply), Anthropic-format for Claude (`tool_use`/`tool_result` blocks); max 5 iterations; per-IP-friendly (no retry storms)
- Modify: `backend/routers/assistant.py` — `/assistant/chat` becomes: build message list from `conversation_history` → tool loop → return text + context. Target: file drops from ~3,100 lines to a few hundred.
- Delete: `backend/services/intent_processor.py` (4,338), `semantic_intent_router.py`, `intent_schema.py`, `dynamic_intent_processor.py`, `intent_processor_integration.py`, `nlp_entity_extractor.py`, obsolete intent tests (`tests/test_enhanced_intents_comprehensive.py`, `tests/test_semantic_intent_router.py`, `backend/tests/test_intent_processor_recruiter_outreach.py`, related files in `backend/utils/resume_parsing/tests/`)
- Modify: `backend/services/service_registry.py` — drop `provide_intent_processor`
- Tests: `backend/tests/test_assistant_chat.py` — chat endpoint with a scripted fake provider (deterministic tool_calls): "find me python engineers" → `search_candidates` invoked → response mentions returned names; "how many candidates" → `list_pipeline`; unknown chit-chat → no tool, plain text

### Task B3: Cleanup sweep

- Grep for imports of every deleted module; fix or delete stragglers (known: agent_framework agents, `routers/matching.py`, `job_service.py` import from `llm_service` — interface preserved so they should be untouched; verify)
- Full suite green; ruff gate green

## Stage C — Eval harness (branch `phase-2c-evals`, one PR)

### Task C1: Synthetic labeled resumes

**Files:**
- Create: `evals/resumes/{001..030}.txt` + `evals/labels/{001..030}.json` — ~30 synthetic resumes (varied: tech/non-tech, military, career-change, sparse, dense, unusual formats) with hand-checked ground truth (name, email, phone, titles, companies, date ranges, skills, education)
- Generate via the cheapest available tier (local qwen3:8b or OpenRouter), then hand-verify labels. Synthetic-only policy holds (spec §6).

### Task C2: Scorer + comparison table

**Files:**
- Create: `evals/scorer.py` — field-level accuracy: exact-match for email/phone, fuzzy (normalized) for names/titles/companies, set-F1 for skills
- Create: `evals/run_eval.py` — runs each fixture through: regex baseline (`RegexExtractor`), qwen3:8b, OpenRouter default, `claude-haiku-4-5`; records accuracy, latency, cost estimate; writes `evals/results.md` table
- Create: `backend/tests/test_eval_scorer.py` — scorer unit tests on toy inputs (pytest, runs in CI); the live eval run itself is manual (`python evals/run_eval.py`), not CI
- Modify: `README.md` — publish the comparison table + per-task routing decision (spec §7 table)

### Task C3: Routing decision

- Set `llm_provider_order` per task type from the results (resume parsing = benchmark winner; chat = cheapest adequate) and record the decision in `docs/decisions/` as an ADR

---

## Verification gates (every stage)

1. `poetry run pytest` green locally against docker pg on 5433
2. `poetry run ruff check .` clean
3. Boot the app, hit `/api/jobs/{id}/matching-candidates` — top match unchanged (97.4% Data Engineer baseline)
4. CI green on the PR before merge
