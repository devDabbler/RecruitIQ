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

A FastAPI backend (92 routes) and a Streamlit frontend, backed by a single
PostgreSQL database with `pgvector`.

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

---

## Honest status

This is a portfolio piece under active renovation, not a product. Being
specific about what is broken is more useful to you than a feature list:

- **Neo4j is gone.** It held 48 nodes and its vector indexes were
  misconfigured — 384-dimension indexes against 1536-dimension stored vectors —
  so the "graph layer" was concept, not capability. Phase 1b deleted it
  (~5,400 lines net, 31 packages including LangChain and the entire PyTorch
  stack) and rebuilt the vector layer on Postgres + `pgvector`: 768-dimension
  embeddings, HNSW indexes, working semantic search. `docker compose up -d db`
  is now the whole database story.
- **The Nebius API key is dead (HTTP 401)** and it is still the primary
  provider, so AI-dependent paths fail until the provider chain is rebuilt
  (Phase 2). Its doomed connection test also dominates the ~27 s first-request
  warmup.
- **`intent_processor.py` is 4,338 lines of hand-written regex** across 30+
  intents. It is being replaced with ~8 tool definitions.
- **The test suite:** 65 passing, 0 failing, 86 skipped, with CI (ruff +
  pytest against a pgvector service container) on every PR. See
  [documentation/TESTING.md](documentation/TESTING.md).

Full assessment and plan:
[docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md](docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md).

---

## Running it

Requires **Python 3.11+**, Poetry and Docker. Redis and MinIO are optional —
the app degrades gracefully without them.

```bash
poetry install
cp .env.example .env        # fill in POSTGRES_* at minimum
docker compose up -d db     # pgvector Postgres on :5433
cd backend && poetry run alembic upgrade head && cd ..
```

```bash
# Terminal 1 - backend on :8000
poetry run python -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend

# Terminal 2 - frontend on :8501
poetry run streamlit run frontend/app.py
```

API docs at `http://localhost:8000/docs`. To embed seed data for semantic
search: `poetry run python scripts/backfill_embeddings.py`.

The first request takes around 27 seconds while the parsing subsystem warms
up. Subsequent requests are under 100 ms.

---

## Data

All candidate data in this repository is **synthetic**. Real resumes are
excluded by `.gitignore` and are never committed.

## License

[MIT](LICENSE)
