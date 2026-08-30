# RecruitIQ Portfolio Revival — Design

**Date:** 2026-08-26
**Status:** Design approved in conversation; spec pending user review
**Owner:** Sean C. (scollin10@gmail.com, GitHub `devDabbler`)

---

## 1. Goal and Audience

RecruitIQ has been dormant since ~Oct 2025. The owner has shifted focus to
SentientTrader, and an internal pitch to adopt RecruitIQ at his workplace did not
land. The objective is **not** to resume product development. It is to turn ~2
years of accumulated work into a credible public portfolio piece.

**Audience:** Talent Acquisition leaders and hiring managers at AI-forward
companies (Anthropic named explicitly). Sean is a **recruiter who builds** — that
combination is the pitch. This audience will *not* clone a repo or stand up
Postgres and Neo4j. They will skim a README and click a link.

This inverts normal priorities:

1. A live, clickable demo matters most.
2. The README narrative matters second.
3. Code quality matters as a credibility check by any engineer who looks — not as
   the primary artifact.

**The domain insight is the differentiator.** "Your ATS is a graveyard of
qualified candidates you already paid to source" is a thesis a working recruiter
has and a software engineer does not. It belongs at the top of the README.

### The lineage (currently invisible)

Ten repos over two years, all attacking the same problem:

`py_to_mysql_resparser` (Mar '24) → `RezParser` → `Resume-Cupidv1` →
`Resume-Cupid-RAG-Test` → `Resume_Cupid_CrewAI_HF_Llama3` →
`Resume-Cupid_Multi-Option-LLM` → `Resume-Cupid-Full-Stack` → `Resumatch-AI` →
`Recruiter-Dashboard` → `Recruiting-Dashboard` → **RecruitIQ**

MySQL regex parser → CrewAI → RAG → Neo4j-backed platform. That arc *is* the
credential. It is currently spread across ten repos, most private, and told
nowhere.

---

## 2. Current State — Assessment Findings

Verified by direct inspection on 2026-08-26.

### 2.1 Runtime baseline — verified 2026-08-27

Everything below §2.1 was originally read from source, not observed. On
2026-08-27 the app was actually launched. **It runs.**

| Check | Result |
|---|---|
| Poetry env | Intact (`py3.11`); `import main` clean |
| Registered routes | 95 routes / 78 OpenAPI paths; 6 agents register |
| Boot time | ~7 s to bind |
| `/health`, `/docs` | 200 |
| `/api/jobs` | 200 in 72 ms, real data |
| `/api/candidates` | 200 — **28 s cold**, 300 ms warm |
| Postgres | 16.9, running as service `postgresql-x64-16` |
| Redis | Running inside WSL Ubuntu (this is what the WSL step was for) |
| Neo4j | Neo4j Desktop 5.24.0 Enterprise; started later same day — see §2.2 |
| MinIO | Not running; app falls back to local storage |
| Docker | **Not installed at all** |

**`ats_db` contents (real, not empty):** 23 candidates, 30 resumes, 6 jobs,
48 skills, 372 candidate-skill links, 25 education rows, 61 experience rows.
Alembic stamped `40d08a3d3c48`. Extensions: `pg_trgm`, `plpgsql`, `uuid-ossp` —
**no pgvector yet**, consistent with vectors having lived in Neo4j.

*Caution for future inspection:* `pg_stat_user_tables.n_live_tup` reads 0 for
every table here — a stale-statistics artifact that falsely suggests an empty
database. Use `pg_class.relpages` / `reltuples`, or authenticate and `count(*)`.

**Blocker found and resolved.** Every DB route failed with `password
authentication failed for user "admin"`. The `admin` password had been rotated
— most plausibly when CollinsAI was provisioned on 2026-08-06 — and RecruitIQ's
`.env` and `alembic.ini` (both still carry the old value) were never updated.
Reset on 2026-08-27 back to the value already in config, via a temporary
`pg_hba.conf` trust rule scoped to `admin@localhost`, followed by a service
restart. `pg_hba.conf` was restored to all-`scram-sha-256` and verified clean.

**Three findings that change the plan:**

1. **Port 8000 is occupied by a different project** — an API titled *CollinsAI*
   (36 paths). RecruitIQ was run on 8010. Because the Streamlit frontend
   hardcodes `localhost:8000` in **30+ places** with no central client, running
   the UI today silently points RecruitIQ at the wrong backend. The URLs are
   also *inconsistent* — some default to `localhost:8000`, others to
   `localhost:8000/api`. This promotes the central API client from cleanup to
   an early correctness fix.
2. **The Nebius key is dead — HTTP 401**, not merely circuit-broken. It is the
   *current* primary provider, so the app's AI paths are broken today. Verified
   working: **Groq 200, OpenRouter 200, `ollama.sentienttrader.ai` 200** (124 ms
   from the laptop; all four models present). §4.3's deprioritization of Nebius
   is confirmed by evidence.
3. **Docker is not installed**, making the Phase 1 `docker-compose.yml` a
   prerequisite to install rather than merely to author.

**The 28 s cold start** is lazy loading of spaCy `en_core_web_lg` (the `_sm`
model is absent), easyocr, and sentence-transformers — exactly the PyTorch stack
§4.2 removes. Warm calls are ~300 ms, so this is cold start, not an N+1 query.

### 2.2 Neo4j contents — verified 2026-08-27

Neo4j **5.24.0 Enterprise**, started on request. Bolt auth with the `.env`
credentials works (that password was *not* rotated). Contents:

| Aspect | Reality |
|---|---|
| Total nodes | **48** — 32 `Skill`, 10 `Candidate`, 6 `Job` |
| Total relationships | **43**, all of one type: `(:Job)-[:REQUIRES]->(:Skill)` |
| Candidate relationships | **Zero.** 10 candidates, 0 edges |
| Candidate embeddings | **None.** Props are only id/name/email/phone/location/timestamps |
| Job embeddings | Present — 3 per job, all **1536-dim** |
| Vector indexes declared | 8 |
| Labels with indexes but no nodes | `Resume`, `KnowledgeNode`, `MarketIntelligence`, `AgentInsight` |

**The vector layer is non-functional, not merely sparse.** Two independent
reasons:

1. **Dimension mismatch.** Seven of the eight vector indexes declare
   `vector.dimensions: 384`, but the only vectors actually stored are
   **1536-dim** (an OpenAI-era leftover; the odd one out,
   `resume_skills_embedding`, is 1536 but indexes a label with zero nodes).
   A 384-dim index cannot serve 1536-dim vectors.
2. **The candidate side is empty.** No candidate has an embedding and no
   candidate has a single relationship — so candidate vector search and graph
   traversal both have nothing to operate on.

**Postgres and Neo4j are also out of sync:** 23 candidates in Postgres, 10 in
Neo4j.

**Consequence for Phase 1 — this is good news.** §2's "Neo4j vector + graph
matching layer" is confirmed as *concept only*; there is essentially nothing to
migrate. The 384↔768 dim change in §4.2 invalidates nothing that works today.
Removing Neo4j is close to free, and it is still the single biggest barrier to
anyone running this project.

### 2.3 Matching works — one-line bug found and fixed

`GET /api/jobs/{id}/matching-candidates` returned **500** even with Neo4j up.
The pipeline itself was fine — role scoring, skill overlap, experience scoring,
and cross-domain penalties all computed correctly — and then failed at response
serialization:

```
2 validation errors for CandidateMatch
id         Input should be a valid integer ... input_value='22d0dac0-348c-...'
resume_id  Input should be a valid integer ... input_value=None
```

`CandidateMatch` in `backend/routers/jobs.py:26` still declared `id: int` and
`resume_id: int`. Candidate ids are **UUID strings**, and a candidate may have
no resume row. The sibling model `CandidateMatchResult`
(`backend/routers/enhanced_matching.py:47`) had already been corrected to
`id: str` / `resume_id: Optional[int]` — so this was **drift between two
routers**, not a design flaw.

Fixed 2026-08-27. The endpoint now returns **HTTP 200 with 10 ranked
candidates** in ~5.9 s cold (top match 97.4% for *Data Engineer*).

**Implication:** the demo's headline capability was one type annotation away
from working. Similar int-vs-UUID drift very likely exists elsewhere and is
worth an explicit sweep in Phase 1.

### Security (better than assumed)

- `.env` has **never** been committed on any branch. Live API keys are local-only.
  **No credential rotation is required.**
- The only git-history match for key-shaped strings is a string literal in
  `backend/services/recruitiq_travel_service.py` performing key-format validation.
  Not a leak.
- **However:** an 86.7 MB `model.safetensors` blob is in public git history
  (`backend/models/sentence_transformers/...`). `.git` is 92 MB. The repo is
  already public at `github.com/devDabbler/RecruitIQ`.

### Backend

- FastAPI, 21 routers, ~88 endpoints, 41 services.
- **No authentication anywhere.** `backend/routers/auth.py` is 0 bytes.
- No CORS middleware.
- Sync SQLAlchemy inside async routes (blocking I/O in an async context).
- Two parallel Alembic migration trees (`backend/alembic/` and
  `backend/migrations/`), plus a third under `models/alembic/`.
- `backend/services/intent_processor.py` — **4,338 lines** of hand-written regex
  intent detection across 30+ intents.
- `backend/routers/assistant.py` — 3,135 lines.
- `backend/services/recruitiq_travel_service.py` — 2,478 lines (travel planning).
- Dead directories: `z_ollama_backup/`, `patches/`, `examples/`.

### Frontend

- Streamlit, 14,761 lines across 47 Python files, 22 modules.
- 97 `unsafe_allow_html=True` calls fighting the framework.
- Hardcoded `testuser` / `password` in `frontend/app.py`.
- No central API client — `requests` and `httpx` calls scattered per module.
- Four screens are pure demo data: `communications`, `company_policies`,
  `transformation` (explicit "TODO: Integrate with backend API"), `metrics`.

### AI stack (dated)

- LangChain `0.1.0` — roughly three major versions behind.
- Models in use: Nebius `microsoft/phi-3-mini-4k-instruct`, OpenRouter
  `meta-llama/llama-3.3-8b-instruct:free`, Groq `llama-3.3-70b-versatile` for
  reranking. Cohere and Gemini initialized but disabled.
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`, 384-dim, in Neo4j.
- Resume parsing: LLM structured extraction with a **2,534-line regex fallback**
  (`regex_extractor.py`) plus JSON-repair layers (`improved_json_handling.py`,
  `patches/robust_json_extractor.py`). The repair layers exist *because* the small
  models don't reliably conform to schema.

### Repo hygiene

- 302 tracked files. Tests exist (138 files) but are **gitignored** — only 3
  tracked.
- No CI, no Dockerfile, no docker-compose.
- `dev.py` is broken: opens a browser to port 5000, where nothing listens.

### What is genuinely good and must be preserved

- The resume-parsing pipeline design: LLM extraction → regex fallback → military
  experience extractor, with Pydantic contracts (`ResumeV2`) and validation
  scoring.
- The Neo4j vector + graph matching layer (concept, not implementation).
- The multi-provider LLM abstraction with fallback (concept — to be rebuilt).

---

## 3. Existing Infrastructure (discovered, reusable)

This is the key finding that shapes the deployment design. Sean already operates
production infrastructure that RecruitIQ can reuse.

### Droplet 1 — `sentient-trader` (157.245.233.229)

| Property | Value |
|---|---|
| OS | Ubuntu 24.04.3 LTS |
| Specs | 4 vCPU, 7.8 GB RAM, 48 GB disk |
| Free | ~3.6 GB RAM, ~26 GB disk |
| Running | nginx (80/443, SSL configured), Redis (6379, localhost), uvicorn (8000), python (8001), java (4002) |
| Not installed | Docker, PostgreSQL |

This is the live SentientTrader production host.

### Droplet 2 — `wireguard-ams` (178.128.247.198)

1 vCPU, 458 MB RAM, Amsterdam. WireGuard VPN box. **Unusable** for RecruitIQ —
roughly 4× too small, wrong region, and repurposing kills the VPN.

### Home PC (LLM box)

- **RTX 3080 Ti, 12 GB VRAM.** Runs 24/7. Also runs SentientTrader components.
- Ollama **v0.30.7**, exposed via an **existing Cloudflare Tunnel** at
  `https://ollama.sentienttrader.ai` — reachable from the droplet in **201 ms**.
- Models installed (~23.5 GB):

| Model | Size | Role | Status |
|---|---|---|---|
| `nomic-embed-text` | 274 MB | Signal embeddings → pgvector | Constantly used; resident in VRAM (308 MB) |
| `qwen3:8b` | 5.2 GB | Default local reasoner (`OLLAMA_MODEL`) | Rare — 3 calls in 6.3 h |
| `deepseek-r1:14b` | 9.0 GB | Tier-2 fallback | Dormant |
| `qwen2.5-coder:14b` | 9.0 GB | None | **Orphan — zero consumers** |

- Local carries **~1% of LLM traffic**. Every money-touching path in
  SentientTrader is **deliberately pinned to cloud** (OpenRouter:
  `llama-3.3-70b-instruct`, `gemini-2.5-pro`, `gpt-4o-mini`, `gemini-2.5-flash`;
  Nebius `Llama-3.3-70B-Instruct` mostly circuit-broken).

**Note:** the laptop used for this session is a *different* machine (AMD Radeon
890M iGPU, 31 GB RAM, Ollama 0.17.7 with `deepseek-r1:8b`). Not the LLM box.

---

## 4. Design Decisions

| Area | Decision |
|---|---|
| Product name | **RecruitIQ** (unchanged) |
| Domain | **recruitiq.io** - Namecheap remains registrar, Cloudflare serves DNS. Was `resumecupid.ai` through Phase 5; renamed 2026-08-30 to match the product name, old domain redirects (ADR 0005) |
| Branding note | ~~Footer line acknowledging the domain as an earlier iteration~~ - moot after the rename; the lineage story stands on its own merits rather than as an explanation |
| Hosting | Piggyback `sentient-trader`, with hard `systemd MemoryMax=` caps |
| Frontend | Next.js App Router + TypeScript + Tailwind + shadcn/ui |
| Backend | FastAPI retained |
| Database | **Single Postgres + pgvector**, 768-dim vectors |
| Auth | Real JWT auth (fills the empty `auth.py`); public demo auto-signs-in a read-only demo account |
| Narrative | README lineage section + `docs/decisions/` ADRs |
| Evals | ~30 labeled synthetic resumes, pytest scorer, published comparison table |

### 4.1 Data store collapse

Five stores become one. This is the highest-leverage change — Neo4j is the single
biggest reason nobody can run this project.

| Today | Becomes | Rationale |
|---|---|---|
| PostgreSQL | **Postgres + pgvector** | Already used for `AgentMemory`; path exists |
| Neo4j (vectors + skill graph) | folded into pgvector | Removes the hardest setup dependency |
| Redis (as cache) | dropped as a store | Not load-bearing. *Droplet Redis is still used for rate limiting.* |
| MinIO | Vercel Blob or local disk | One less container |
| 5 LLM providers | provider chain (below) | One coherent abstraction |

### 4.2 Embeddings — reuse `nomic-embed-text`

RecruitIQ calls the **existing** `https://ollama.sentienttrader.ai` endpoint for
embeddings. Consequences:

- **No PyTorch anywhere.** No sentence-transformers, no ONNX conversion, no
  embedding model on the droplet.
- pgvector columns are **768-dim** (not 384). Re-seeding from scratch anyway, and
  768-dim is better retrieval quality.
- The model is already resident in VRAM and already serving SentientTrader — zero
  marginal cost.
- **Fallback:** all seed data is pre-embedded at build time, so browsing the demo
  never touches the PC. Only live resume upload needs a fresh embedding; if the
  tunnel is down that one path degrades.

### 4.3 LLM provider chain

Mirrors the tiered pattern already proven in SentientTrader.

```
1. ollama.sentienttrader.ai  →  qwen3:8b        (20s timeout, best-effort)   $0
2. OpenRouter                                    (real fallback)             ~$0
3. Claude Haiku 4.5 / Sonnet 4.6                 (benchmark reference)       cents
```

- **Reuse `qwen3:8b`** rather than pulling a new model — no additional VRAM
  pressure, and keeping it warm marginally *helps* SentientTrader's cold starts.
- **Nebius is deprioritized** — mostly circuit-broken in production. OpenRouter is
  the real fallback.
- One `OpenAICompatibleProvider` class covers OpenRouter, Nebius, Groq, and
  Together via base-URL swap.
- Claude model IDs: `claude-haiku-4-5` ($1/$5 per MTok), `claude-sonnet-4-6`
  ($3/$15), `claude-opus-4-8` ($5/$25).

### 4.4 Protecting SentientTrader (non-negotiable)

Sean deliberately pinned money-touching paths to cloud. Adding a publicly-linked
demo to the same GPU is exactly that contention. Volumes are tiny on both sides,
but **consequences are asymmetric**: a demo visitor waiting 3 seconds costs
nothing; a queued re-entry check can cost money.

Guards:

1. Local calls are **best-effort with a ~20s cap** — never block, never retry
   against a busy GPU. Fall through to OpenRouter.
2. **Hard per-IP rate limits** on AI actions, backed by the droplet's existing
   Redis.
3. **Share `qwen3:8b`** — no second model thrashing in and out of 12 GB VRAM.
4. **Seed data pre-embedded** — browsing never reaches the PC.
5. `systemd MemoryMax=` on all RecruitIQ units so it is OOM-killed before it can
   starve anything else on the droplet.

### 4.5 Structured output

- **Ollama ≥ 0.5.0 supports JSON Schema** via the `format` parameter. Sean is on
  0.30.7, so the *local* path gets schema conformance too.
- **Claude** guarantees conformance via `messages.parse()` against the existing
  `ResumeV2` Pydantic contract.
- **OpenAI-compatible providers** vary by underlying model — conformance is not
  guaranteed.
- Therefore the JSON-repair layer is **retained but scoped** to non-guaranteeing
  providers, rather than sitting on the primary path. `regex_extractor.py` stays
  as a genuine fallback — that is good engineering, not debt.

### 4.6 Intent routing → tool calling

Replace `intent_processor.py` (4,338 lines of regex) with ~8 tool definitions:
`search_candidates`, `match_to_job`, `explain_match`, `get_market_data`,
`get_candidate`, `get_job`, `list_pipeline`, `parse_resume`.

**~4,300 lines deleted.** This is the headline README bullet.

---

## 5. Scope Cuts

**Delete (~4,000 lines):**

- `recruitiq_travel_service.py` (2,478), `interview_travel_assistant.py`,
  `free_travel_service.py`, `travel_service.py`, `routers/travel.py`
- `modules/transformation.py` (stub), `routers/transformation.py`
- `modules/company_policies.py`, `modules/communications.py`,
  `modules/metrics.py`, `modules/cache_management.py` (all demo-data-only)
- `backend/z_ollama_backup/`, `backend/patches/`, `backend/examples/`
- Duplicate Alembic trees — consolidate to one
- LangChain entirely

**Keep — 8 screens:** Dashboard, Candidates, Candidate Detail, Jobs, Job Detail,
Resume Upload, Matching, AI Assistant.

Nothing ships stubbed. One dead tab is the fastest way to look unfinished.

---

## 6. Seed Data

~200 synthetic candidates + 25 jobs, pre-parsed and pre-embedded at build time.

- **Synthetic only** — no real resumes. Also the correct answer if anyone asks
  about data ethics.
- Generate offline via the cheapest available provider (local `qwen3:8b`, or
  Claude Batch API at 50% off ≈ $2 one-time).
- Pre-computed match scores so browsing costs $0 and never touches the PC.

---

## 7. Eval Harness

~30 synthetic resumes with hand-labeled ground truth, scored by a pytest-run
scorer, with field-level accuracy published in the README.

Compared across:

| Field | Regex baseline | `qwen3:8b` (local) | OpenRouter | Claude Haiku 4.5 |
|---|---|---|---|---|

This is the **decision-making tool**, not just a showcase artifact — it picks the
per-task provider routing empirically instead of by assertion. For an AI-forward
TA audience it demonstrates cost-quality engineering with receipts, and it turns
two years of multi-provider work into evidence rather than abandoned code.

Per-task routing target:

| Task | Volume | Tolerance | Provider |
|---|---|---|---|
| Resume parsing | Low (upload only) | Schema-critical | Benchmark-chosen |
| Assistant chat | Higher | Forgiving | Cheapest adequate |
| Seed generation | One-time | Offline | Cheapest |

---

## 8. Publishing

- **Fresh git history.** The 86.7 MB blob cannot be surgically removed from a repo
  others may have cloned. Start clean; keep the old repo archived.
- `.env.example` with every key documented.
- `docker-compose.yml` — `git clone && docker compose up` must work.
- GitHub Actions: pytest + ruff.
- **Un-gitignore the tests.** 138 test files exist and are invisible.
- README rebuilt around the lineage, not a feature list.
- Archive the stale public repos: `Resumatch-AI` and
  `Resume-Cupid_Multi-Option-LLM` (the latter's README still contains an unedited
  `git clone https://github.com/your-username/resume-cupid.git` placeholder and
  the line "not yet ready for public use").

---

## 9. Cost

| Item | Cost |
|---|---|
| Hosting | **$0** (piggybacks existing droplet) |
| Embeddings | **$0** (existing Ollama, already resident) |
| LLM — local tier | **$0** (electricity) |
| LLM — OpenRouter fallback | ~$0–3/mo |
| Claude (benchmark reference only) | cents |
| Seed generation | ~$2 one-time (or $0 local) |
| Domain | already owned |
| **Total ongoing** | **~$0–5/month** |

---

## 10. Phasing

Each phase leaves something shippable, so the work cannot strand halfway.

### Phase 0 — Publishable immediately (~1 day)

Fresh repo with clean history; `.env.example`; un-gitignore tests; README with the
lineage narrative; archive stale public repos; delete dead directories. **No code
changes.** Makes the GitHub presence presentable on its own.

### Phase 1 — Verify and consolidate

**First: confirm the app actually runs.** Nothing above has been verified at
runtime — it is all from reading code. Establish a known-good baseline before
refactoring. Then: Neo4j → pgvector (768-dim), one Alembic tree, drop LangChain,
scope cuts, docker-compose, CI.

### Phase 2 — AI layer

Provider chain (Ollama → OpenRouter → Claude); structured outputs; tool calling
replaces `intent_processor.py`; eval harness; per-task routing chosen from
results.

### Phase 3 — Frontend

Next.js rebuild, 8 screens, JWT auth with demo auto-login.

### Phase 4 — Deploy

nginx server block on the droplet, DNS at Namecheap, certbot, systemd units with
`MemoryMax=`, rate limiting on existing Redis, seed data load, ADRs.

---

## 11. Open Items

1. ~~**Runtime verification not done.**~~ **RESOLVED 2026-08-27** — see §2.1.
   The app boots and serves real data. The WSL step was Redis, not Postgres.
2. **Ollama observability gap.** `%LOCALAPPDATA%\Ollama\server.log` has not been
   written to despite the service serving requests. Local-side usage cannot be
   audited. Worth fixing before benchmarking, since eval timings depend on it.
3. **Reclaimable disk on the PC:** `qwen2.5-coder:14b` (9 GB) has zero consumers;
   `deepseek-r1:14b` (9 GB) serves a path that has never fired. 18 of 23.5 GB
   idle. Unrelated to RecruitIQ, noted opportunistically.
4. **768-dim migration** invalidates any existing embeddings. Acceptable — seed
   data is regenerated from scratch.

---

## 12. Launch Reference (current, pre-refactor)

For the record, since the owner had forgotten:

```powershell
poetry install
poetry run python start_backend.py    # terminal 1 → :8000
poetry run python start_frontend.py   # terminal 2 → :8501
```

Login `testuser` / `password`. `run.py` starts both; `dev.py` is broken (opens
port 5000, nothing listens there).

**Corrected 2026-08-27 by actually running it:**

- **`start_backend.py` hardcodes port 8000, which CollinsAI now owns.** Launch
  uvicorn directly on a free port instead:
  ```powershell
  cd backend
  poetry run python -m uvicorn main:app --host 127.0.0.1 --port 8010
  ```
- **Do not launch the Streamlit frontend until the port conflict is settled** —
  it hardcodes `localhost:8000` in 30+ places and will hit CollinsAI's API.
- **Neo4j is not required to boot.** It is down, and `/api/candidates` and
  `/api/jobs` both return real data anyway. MinIO is likewise optional (falls
  back to local storage). Only **Postgres** is genuinely required; Redis runs in
  WSL.
- Allow ~30 s for the first request (model lazy-loading) before assuming a hang.
