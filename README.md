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

A FastAPI backend (95 routes) and a Streamlit frontend, backed by PostgreSQL.

**The resume parsing pipeline** is the part I am most confident in. LLM
structured extraction against a Pydantic contract, falling back to a regex
extractor, with a dedicated extractor for military service — because veteran
resumes describe experience in a format civilian parsers reliably mangle.

**Candidate-job matching** scores role fit, skill overlap and experience
independently, then applies cross-domain penalties. A pre-K teacher does not
rank for a Data Engineer role just because both mention "leadership".

---

## Honest status

This is a portfolio piece under active renovation, not a product. Being
specific about what is broken is more useful to you than a feature list:

- **Neo4j is being removed.** It holds 48 nodes and its vector indexes are
  misconfigured — 384-dimension indexes against 1536-dimension stored vectors.
  It is the single biggest barrier to anyone running this project, and it is
  being folded into Postgres with `pgvector`.
- **The Nebius API key is dead (HTTP 401)** and it is still the primary
  provider, so AI-dependent paths fail until the provider chain is rebuilt.
- **`intent_processor.py` is 4,338 lines of hand-written regex** across 30+
  intents. It is being replaced with ~8 tool definitions.
- **The test suite:** 58 passing, 0 failing, 93 skipped. The nine defects
  that were failing visibly after Phase 0 — including a
  character-corruption bug in experience parsing — are fixed. See
  [documentation/TESTING.md](documentation/TESTING.md).

Full assessment and plan:
[docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md](docs/superpowers/specs/2026-08-26-recruitiq-portfolio-revival-design.md).

---

## Running it

Requires **Python 3.11+**, Poetry and PostgreSQL. Neo4j, Redis and MinIO are
optional — the app degrades gracefully without them.

```bash
poetry install
cp .env.example .env        # fill in POSTGRES_* at minimum
```

```bash
# Terminal 1 - backend on :8000
poetry run python -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend

# Terminal 2 - frontend on :8501
poetry run streamlit run frontend/app.py
```

API docs at `http://localhost:8000/docs`.

The first request takes around 30 seconds while spaCy and the OCR models load.
Subsequent requests are around 300 ms.

---

## Data

All candidate data in this repository is **synthetic**. Real resumes are
excluded by `.gitignore` and are never committed.

## License

[MIT](LICENSE)
