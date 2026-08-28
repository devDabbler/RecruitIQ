# RecruitIQ

**Your ATS is a graveyard of qualified candidates you already paid to source.**

Every agency and in-house team I have worked on sits on thousands of resumes
that were good enough to interview and never got called again. The candidate
was real, the skills were real, the money to source them was already spent.
Then the req closed and they vanished into a search index that only matches on
keywords.

RecruitIQ is my attempt to fix that: parse what is already in the pile,
represent it properly, and match against live roles semantically instead of by
string.

I am a recruiter, not a software engineer by training. I have been building
toward this problem for two years.

---

## The lineage

This repository is the eleventh iteration. The arc matters more than any single
repo:

| # | Repo | What it added |
|---|---|---|
| 1 | `py_to_mysql_resparser` (Mar 2024) | Regex parsing into MySQL |
| 2 | `RezParser` | Structured extraction |
| 3 | `Resume-Cupidv1` | First matching attempt |
| 4 | `Resume-Cupid-RAG-Test` | Retrieval-augmented matching |
| 5 | `Resume_Cupid_CrewAI_HF_Llama3` | Multi-agent orchestration |
| 6 | `Resume-Cupid_Multi-Option-LLM` | Provider abstraction |
| 7 | `Resume-Cupid-Full-Stack` | End-to-end application |
| 8 | `Resumatch-AI` | Matching as the product |
| 9 | `Recruiter-Dashboard` | Recruiter-facing workflow |
| 10 | `Recruiting-Dashboard` | Pipeline management |
| 11 | **RecruitIQ** | Graph + vector matching, agent framework |

MySQL regex parser to CrewAI to RAG to a graph-backed platform. Each one taught
me what the previous one got wrong.

---

## What is actually here

A FastAPI backend (92 routes) and a Next.js front end, backed by a single
PostgreSQL database with `pgvector`. The browser only ever talks to Next, which
holds the session cookie and calls FastAPI server-side — so the API listens on
loopback and there is no CORS configuration anywhere.

**The resume parsing pipeline** is the part I am most confident in. LLM
structured extraction against a Pydantic contract, falling back to a regex
extractor, with a dedicated extractor for military service — because veteran
resumes describe experience in a format civilian parsers reliably mangle.

**Candidate-job matching** scores role fit, skill overlap and experience
independently, then applies cross-domain penalties. A pre-K teacher does not
rank for a Data Engineer role just because both mention "leadership".

**Semantic search** embeds every candidate and job as a 768-dimension vector
(`nomic-embed-text`, served by an Ollama instance I already run for another
project) and ranks by cosine similarity in `pgvector`. "Machine learning
engineer with python" surfaces the NLP Engineers first — no keyword overlap
required.

**The AI assistant** is native LLM tool calling: the model reads the
conversation and picks from 8 tool definitions (semantic candidate search,
job matching, match explanation, salary benchmarks, pipeline stats...), each a
thin wrapper over the same services the REST API uses. This replaced a
4,338-line hand-written regex intent processor — the single largest deletion
in the codebase's history, and the code works better.

**The LLM provider chain** runs local-first: a `qwen3:8b` on my own GPU
(best-effort, hard 20-second cap so a demo visitor can never queue work behind
my other project's inference), falling through to OpenRouter, then Claude.
Structured outputs are schema-enforced where the provider supports it (Ollama
`format`, Claude `messages.parse`) and JSON-repaired where it does not — the
repair layer is scoped to exactly the tier that needs it.

**Which model parses resumes is decided by benchmark, not vibes.** The eval
harness (`evals/`) runs 30 synthetic hand-labeled resumes through the exact
production prompt, schema, and token budget, and scores field-by-field:

| | overall | median latency | $/1k resumes |
|---|---|---|---|
| regex baseline | 49% | 0.03s | $0 |
| `qwen3:8b` (local) | 86% | 6.5s | $0 |
| **`gemini-2.5-flash-lite`** | **99%** | **2.6s** | **$0.83** |
| `gpt-5-nano` | 100% | 25.6s | $1.89 |
| `qwen3-32b` | 95% | 31.8s | $0.81 |

So resume parsing — low-volume and schema-critical — routes to
`gemini-2.5-flash-lite`, while chat stays on the free local tier
([ADR 0002](docs/decisions/0002-per-task-llm-routing.md)). gpt-5-nano is the
accuracy winner but spends 10× the wall clock thinking; a first run scored it
53% because a provider bug reported truncated completions as successes —
building the eval found that bug and three others in production code, which
is most of why it was worth building.

---

## Honest status

This is a portfolio piece under active renovation, not a product. Being
specific about what is broken is more useful to you than a feature list:

- **Neo4j is gone.** It held 48 nodes and its vector indexes were
  misconfigured — 384-dimension indexes against 1536-dimension stored vectors —
  so the "graph layer" was concept, not capability. Phase 1b deleted it
  (~5,400 lines net, 31 packages including LangChain and the entire PyTorch
  stack) and rebuilt the vector layer on Postgres + `pgvector`: 768-dimension
  embeddings, working semantic search. `docker compose up -d db` is now the
  whole database story.
- **The AI layer was rebuilt in Phase 2.** The dead Nebius provider (HTTP 401
  on the primary path) and the 4,338-line regex intent processor are both
  gone, replaced by the provider chain and tool calling described above.
  Net across Phase 2: roughly 10,000 lines of provider spaghetti,
  intent regex, and their tests deleted.
- **The Streamlit app is gone.** Phase 3 replaced it with Next.js: eight
  screens, JWT in an httpOnly cookie, visitors auto-signed-in as a read-only
  demo user so a link from my résumé lands in a working product rather than a
  login form. TypeScript types are generated from the committed `openapi.json`,
  so a screen reading a field the API no longer returns fails the build instead
  of rendering a blank card. Deleting the old app also dropped nine declared
  dependencies nothing outside it imported — `streamlit` and its two add-ons,
  `pandas`, `scipy`, `plotly`, `altair`, `matplotlib`, `pyperclip` — which is
  27 packages once transitives are counted.
- **The test suite:** 269 passing Python tests plus 36 front-end unit tests and
  a Playwright journey through all eight screens. CI runs ruff, pytest against
  a pgvector service container, and typecheck/lint/test/build for the web app
  on every PR. See [documentation/TESTING.md](documentation/TESTING.md).

Full assessment and plan:
[docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md](docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md).

---

## Running it

Requires **Python 3.11+**, Poetry, Node 20+ and Docker. Redis and MinIO are
optional — the app degrades gracefully without them.

```bash
poetry install
cp .env.example .env        # fill in POSTGRES_* at minimum
docker compose up -d db     # pgvector Postgres on :5433
cd backend && poetry run alembic upgrade head && cd ..
npm --prefix web install
```

```bash
# Terminal 1 - API on :8010, loopback only
poetry run python -m uvicorn main:app --host 127.0.0.1 --port 8010 --app-dir backend

# Terminal 2 - the app on :3000
npm --prefix web run dev
```

Open `http://localhost:3000`; API docs are at `http://localhost:8010/docs`.
For a populated demo: `poetry run python scripts/seed_demo.py`, then
`poetry run python scripts/backfill_embeddings.py` to embed it for semantic
search.

The first matching request takes a few seconds while embeddings and matcher
caches warm; after that, requests are under 100 ms. (The infamous 27-second
cold start died with the Nebius provider in Phase 2.)

---

## Data

All candidate data in this repository is **synthetic**. Real resumes are
excluded by `.gitignore` and are never committed.

## License

[MIT](LICENSE)
