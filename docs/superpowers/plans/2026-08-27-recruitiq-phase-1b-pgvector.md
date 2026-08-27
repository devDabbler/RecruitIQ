# RecruitIQ Phase 1b — Neo4j → pgvector, LangChain Removal, Docker Compose, CI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the two hardest dependencies (Neo4j and LangChain), replace the embedding layer with the existing `ollama.sentienttrader.ai` endpoint at 768 dimensions stored in pgvector, and put the project on Docker Compose + GitHub Actions CI.

**Architecture:** The spec (§2.2) established that Neo4j's vector layer is *concept only* — 48 nodes, zero candidate edges, dimension-mismatched indexes. Verified during planning: the demo's headline endpoint (`GET /api/jobs/{id}/matching-candidates`) runs entirely on Postgres ORM + `MatchingEnhancer` heuristics; `MatchingIntegrator` uses `RAGService` for exactly one attribute (`embedding_adapter`). So this phase **deletes** `graph_service.py` (1,070 lines) and `rag_service.py` (1,400 lines) rather than porting them, swaps the embedding adapter internals from sentence-transformers (384-dim, PyTorch) to an httpx client for Ollama `nomic-embed-text` (768-dim, zero local ML deps), and adds pgvector columns + similarity search as the replacement vector layer. Local dev Postgres moves into a Docker container (`pgvector/pgvector:pg16` on host port **5433**) because installing pgvector into the Windows service Postgres requires compiling with MSVC — the container is also the reproducible story the repo needs, and the Windows service on 5432 stays untouched for CollinsAI.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pgvector (`pgvector` Python pkg already a dep), httpx (already a dep), Docker Compose, GitHub Actions, Poetry.

**Verified facts this plan relies on (do not re-derive):**
- `MatchingIntegrator.__init__` uses `rag_service` ONLY for `rag_service.embedding_adapter` (matching_integrator.py:25). All matching logic is Postgres ORM + heuristics.
- `MatchingEnhancer(embedding_model=None)` already tolerates a missing embedding model (matching_enhancer.py:18).
- `llm_service._initialize_meta_llama()` is a hard-disabled no-op (`self.meta_llama_model = None`, llm_service.py:675-681), so every `if self.meta_llama_model:` block is dead code and the `langchain_groq`/`langchain_core` imports are removable without behavior change.
- `backend/routers/assistant.py:2618-2619` calls `MatchingIntegrator()` with **no arguments** — currently a latent TypeError; the new signature fixes it.
- The legacy `backend/services/agent_framework/candidate_matching_agent.py` (root level, self-constructs RAGService) is imported by **nobody** — `agent_framework/__init__.py` imports `.agents.candidate_matching_agent` (the DI version used by `AgentFactory`).
- `intent_processor.py:3347` accesses `registry.graph_service` behind `hasattr(registry, 'graph_service')` — removing the property degrades gracefully.
- The embedding surface is duck-typed: consumers call `.encode(text) -> np.ndarray` (via `cache_utils.get_embedding_cached`), `.embed_query(text) -> list`, `.embed_documents(texts) -> list[list]`. Consumers: `intent_processor.py:2815`, `job_service.py:84/270`, `agent_memory_manager.py:14`, `matching_enhancer` (optional).
- PyTorch stack is confined: `sentence_transformers` behind lazy import in `llm_service.py:181`; `easyocr`/`torch`/`torch_directml` behind try/except in `ocr_processor.py:48-84` with a "not available" warning path; pytesseract remains as the other OCR engine.
- The project env is **Poetry** (`poetry run ...`); repo has no `.venv`. Postgres admin password was rotated 2026-08-27 and lives only in `.env`.
- `pytest.ini` testpaths: `backend` and `.`; root `conftest.py` force-imports every backend submodule at collection — any surviving module with a top-level import of a removed package breaks collection.
- Baseline Alembic revision is `716ed00c4df0`; live DB is stamped to it; `agent_memories` does NOT exist in the live DB (no pgvector there).

**Suite baseline going in: 58 passed / 0 failed / 93 skipped (+1 xfail, 1 xpass).** Route count 95. Every task must end at least this green.

---

### Task 1: Branch setup

**Files:** none (git only)

- [ ] **Step 1: Create the working branch from a clean main**

```powershell
git status                    # expect: clean tree on main
git checkout -b phase-1b-pgvector
```

- [ ] **Step 2: Record the baseline**

```powershell
poetry run pytest -q 2>&1 | Select-Object -Last 5
```

Expected: `58 passed, 93 skipped` (+1 xfailed, 1 xpassed). If not, STOP and investigate before changing anything.

---

### Task 2: Remove LangChain from crawler_service

The custom drop-in already exists: `backend/utils/text_splitter.py` defines `CustomTextSplitter(chunk_size, chunk_overlap, separators, keep_separator)` with the same `split_text(text) -> List[str]` surface.

**Files:**
- Modify: `backend/services/crawler_service.py:51-60`
- Test: `backend/tests/test_crawler_text_splitter.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_crawler_text_splitter.py`:

```python
"""Crawler must chunk text without langchain installed."""
import sys


def test_crawler_uses_custom_text_splitter(monkeypatch):
    # Simulate langchain being absent so a regression back to it fails loudly
    monkeypatch.setitem(sys.modules, "langchain", None)
    monkeypatch.setitem(sys.modules, "langchain.text_splitter", None)

    from backend.services.crawler_service import CrawlerService
    from backend.utils.config import Settings

    service = CrawlerService(Settings())
    assert service.text_splitter is not None, "text_splitter must not depend on langchain"

    chunks = service.text_splitter.split_text("para one\n\n" + ("word " * 400) + "\n\npara two")
    assert len(chunks) >= 2
    assert all(len(c) <= 1200 for c in chunks)  # chunk_size 1000 + tolerance for overlap boundaries
```

- [ ] **Step 2: Run it — expect failure**

```powershell
poetry run pytest backend/tests/test_crawler_text_splitter.py -v
```

Expected: FAIL — `service.text_splitter is None` (the monkeypatched langchain import raises, current code sets `None`).

(If `CrawlerService(Settings())` fails on an unrelated constructor requirement, check `crawler_service.py`'s `__init__` signature and adapt the instantiation — the assertion targets are the two lines above.)

- [ ] **Step 3: Swap the import**

In `backend/services/crawler_service.py`, replace lines 51-60:

```python
        # Setup text splitter for chunking content if needed
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separators=["\n## ", "\n### ", "\n#### ", "\n", ". ", ", ", " ", ""],
            )
        except ImportError:
            self.text_splitter = None
```

with:

```python
        # Setup text splitter for chunking content if needed
        from backend.utils.text_splitter import CustomTextSplitter
        self.text_splitter = CustomTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n## ", "\n### ", "\n#### ", "\n", ". ", ", ", " ", ""],
        )
```

Also remove the now-unneeded `if self.text_splitter:` guard's else-branch at ~line 448-459 ONLY if it exists as a dead fallback — read the surrounding function first; if the fallback also handles empty text, leave it.

- [ ] **Step 4: Run the test — expect pass**

```powershell
poetry run pytest backend/tests/test_crawler_text_splitter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/services/crawler_service.py backend/tests/test_crawler_text_splitter.py
git commit -m "refactor: crawler uses in-repo text splitter, not langchain"
```

---

### Task 3: Remove LangChain and dead Meta Llama paths from llm_service

Meta Llama is hard-disabled (`_initialize_meta_llama` always sets `None`), so all its branches are dead. Keep `ModelType.META_LLAMA_MAVERICK` in the enum — callers pass it as a default arg.

**Files:**
- Modify: `backend/services/llm_service.py`

- [ ] **Step 1: Delete the langchain_groq import block (lines 149-153)**

Remove:

```python
try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None
    logging.warning("langchain_groq package not found, Meta Llama functionality will be limited")
```

- [ ] **Step 2: Delete the dead Meta Llama branch in `generate_text` (lines ~500-511)**

Remove:

```python
        # For other tasks or if Nebius AI failed, use Meta Llama
        if hasattr(self, "meta_llama_model") and self.meta_llama_model:
            try:
                logger.info("Sending prompt to Meta Llama model...")
                # The response from invoke is an AIMessage object
                response_message = await self.meta_llama_model.ainvoke(prompt)  # type: ignore

                # The actual text is in the `content` attribute
                return response_message.content  # type: ignore
            except Exception as e:
                logger.error(f"Error generating text with Meta Llama: {e}")
                # Continue to fallbacks instead of raising
```

- [ ] **Step 3: Delete the dead Meta Llama branch in `generate_text_async` (lines ~632-649)**

Remove:

```python
        # Use Meta Llama as secondary option (if available and enabled)
        if self.meta_llama_model:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage

                messages = []
                if system_message:
                    messages.append(SystemMessage(content=system_message))
                messages.append(HumanMessage(content=prompt))

                logger.info("Sending prompt to Meta Llama model...")
                # The response from invoke is an AIMessage object
                response_message = await self.meta_llama_model.ainvoke(messages)  # type: ignore

                # The actual text is in the `content` attribute
                return response_message.content  # type: ignore
            except Exception as e:
                logger.error(f"Error generating text with Meta Llama: {e}")
```

Note: the following `elif self.nebius_ai_service:` (~line 664) may be chained to a `if self.cohere_client:` — after deleting the Meta Llama block, confirm the `if/elif` chain still parses (the Cohere `if` remains the head of the chain; no change needed unless the deleted block was the head).

- [ ] **Step 4: Delete the Meta Llama branch in `get_llm` (lines ~353-356) and `_initialize_meta_llama` (lines ~675-681)**

In `get_llm`, remove:

```python
        elif model_name == ModelType.META_LLAMA_MAVERICK.value:
            # Lazy initialize Meta Llama
            self._initialize_meta_llama()
            return self.meta_llama_model
```

Then remove the whole `_initialize_meta_llama` method. Keep `self.meta_llama_model = None` in `__init__` and the `initialize()` status check — they are harmless and other code reads the attribute defensively.

- [ ] **Step 5: Verify no langchain references remain in the file, and the suite is green**

```powershell
poetry run python -c "import re; s=open('backend/services/llm_service.py',encoding='utf-8').read(); assert 'langchain' not in s.lower(), 'langchain still referenced'; print('clean')"
poetry run pytest -q 2>&1 | Select-Object -Last 3
```

Expected: `clean`, then `59 passed` (58 baseline + Task 2's new test), 0 failed.

- [ ] **Step 6: Commit**

```powershell
git add backend/services/llm_service.py
git commit -m "refactor: remove langchain imports and dead Meta Llama paths from llm_service"
```

---

### Task 4: Delete the Neo4j layer

The big one. Deletions first, then the small edits that unhook them. After this task the app must still boot and the matching endpoint must still return 200 — matching never actually used Neo4j.

**Files:**
- Delete: `backend/services/graph_service.py`, `backend/services/rag_service.py`, `backend/utils/neo4j_vector_custom.py`, `backend/utils/neo4j_vector_monkeypatch.py`, `backend/services/agent_framework/candidate_matching_agent.py` (root-level legacy — NOT the one in `agents/`), `backend/api/routes/job_embeddings.py`, `start_neo4j.py`, `backend/tests/setup_experience_tables.py`, `backend/tests/test_enhanced_matching_fix.py`
- Modify: `backend/services/matching_integrator.py:9-25`, `backend/services/service_registry.py`, `backend/services/job_service.py`, `backend/routers/jobs.py`, `backend/routers/matching.py`, `backend/main.py`, `backend/database/db_connection.py`, `backend/utils/candidate_analyzer.py:19`, `backend/utils/config.py:52-56`, `.env`, `.env.example`, `frontend/modules/assistant.py:350-374,466-469`

- [ ] **Step 1: Delete the files**

```powershell
git rm backend/services/graph_service.py backend/services/rag_service.py backend/utils/neo4j_vector_custom.py backend/utils/neo4j_vector_monkeypatch.py backend/services/agent_framework/candidate_matching_agent.py backend/api/routes/job_embeddings.py start_neo4j.py backend/tests/setup_experience_tables.py backend/tests/test_enhanced_matching_fix.py
```

(`setup_experience_tables.py` is a data-seeding script that imports RAGService — conftest's force-import would break collection. `test_enhanced_matching_fix.py` imports `provide_rag_service` and the nonexistent `provide_matching_service`; it is already broken and its subject matter is covered by the matching endpoint check in Step 9.)

- [ ] **Step 2: Rewire MatchingIntegrator to take the embedding model directly**

In `backend/services/matching_integrator.py`, replace lines 9-25:

```python
from .matching_enhancer import MatchingEnhancer
from .rag_service import RAGService

logger = logging.getLogger(__name__)

class MatchingIntegrator:
    """Integrates advanced matching capabilities with existing services."""
    
    def __init__(self, rag_service: RAGService):
        """
        Initialize the matching integrator.
        
        Args:
            rag_service: The RAG service instance for database access
        """
        self.rag_service = rag_service
        self.enhancer = MatchingEnhancer(embedding_model=rag_service.embedding_adapter)
```

with:

```python
from .matching_enhancer import MatchingEnhancer

logger = logging.getLogger(__name__)

class MatchingIntegrator:
    """Integrates advanced matching capabilities with existing services."""

    def __init__(self, embedding_model=None):
        """
        Args:
            embedding_model: optional adapter with encode/embed_query/embed_documents,
                used by MatchingEnhancer for semantic scoring. Matching works without it.
        """
        self.enhancer = MatchingEnhancer(embedding_model=embedding_model)
```

(This also fixes the latent `MatchingIntegrator()` no-arg call at `backend/routers/assistant.py:2618`.)

- [ ] **Step 3: Clean service_registry**

In `backend/services/service_registry.py`:
- Remove imports: `from .rag_service import RAGService` and `from .graph_service import GraphService` (lines 8-9).
- Remove the `graph_service` property (lines 66-70), the `rag_service` property (lines 72-76), `provide_graph_service()` (169-170), and `provide_rag_service()` (172-173).
- Remove `self._graph_service = None` and `self._rag_service = None` from `__init__`.
- Replace the `matching_integrator` property (lines 78-82) with:

```python
    @property
    def matching_integrator(self):
        if self._matching_integrator is None:
            self._matching_integrator = MatchingIntegrator(
                embedding_model=self.llm_service.get_embedding_model()
            )
        return self._matching_integrator
```

- Replace the `job_service` property body (line 87): `JobService(self.llm_service, self.graph_service)` → `JobService(self.llm_service)`.

- [ ] **Step 4: Clean job_service**

In `backend/services/job_service.py`:
- Remove `from .graph_service import GraphService` (line 8).
- Change the constructor (line 55): `def __init__(self, llm_service: Optional[LLMService] = None, graph_service: Optional[GraphService] = None):` → `def __init__(self, llm_service: Optional[LLMService] = None):`, delete `self.graph_service = graph_service` (line 63) and the graph_service doc line.
- `store_job_embeddings` (~lines 74-130, the method computing desc/req/skills embeddings and calling `self.graph_service.store_job`): replace the whole body with a temporary explicit stub — Task 10 rebuilds it on pgvector:

```python
    def store_job_embeddings(self, db, job_id: int) -> bool:
        """Neo4j embedding storage removed in Phase 1b Task 4.
        Reimplemented on pgvector in Phase 1b Task 10."""
        logger.info(f"store_job_embeddings({job_id}): pgvector storage lands in Task 10; no-op for now")
        return False
```

- `find_similar_jobs_by_title` / the method around lines 264-281 calling `self.graph_service.find_similar_jobs(...)`: replace the graph call so the method returns `[]` with a log line (same pattern as above — read the full method first and preserve its signature and return type). Task 10 reimplements it.
- The singleton factory at lines 623-628: remove the `get_graph_service` import and pass — `JobService(llm_service)`.

- [ ] **Step 5: Clean the routers**

`backend/routers/jobs.py`:
- Line 19-23: remove `provide_graph_service` from the import (keep `provide_job_service`, `provide_llm_service`).
- Remove all six `graph_service = Depends(provide_graph_service)` parameters (lines 83, 144, 169, 230, 320, 393, 430 — and the trailing comma on the preceding line where needed). None of those endpoints use the variable.

`backend/routers/matching.py`:
- Remove `from backend.services.rag_service import RAGService` (line 9).
- Remove the `get_rag_service()` function (lines 65-74).
- Remove the commented-out legacy block referencing `rag_service` (lines ~104-118).

`backend/main.py`:
- Remove lines 18-19 (`from backend.utils.neo4j_vector_monkeypatch import ...` and the call).
- Line 32: `from backend.api.routes import job_routes, job_embeddings` → `from backend.api.routes import job_routes`.
- Remove line 75: `app.include_router(job_embeddings.router, tags=["jobs"])  # New job embeddings routes` (drops 3 dead 410 stubs; route count 95 → 92).
- Line 12: remove `"neo4j"` from `loggers_to_quiet` (cosmetic, do it while here).

- [ ] **Step 6: Clean db_connection, candidate_analyzer, config, .env**

`backend/database/db_connection.py`: remove the neo4j import (lines 18-20), the NEO4J_* env reads (32-36), `get_neo4j_connection()` (81-96), and `execute_neo4j_query()` (127-149). Keep all Postgres functions.

`backend/utils/candidate_analyzer.py` line 19: `from backend.database.db_connection import get_postgres_connection, get_neo4j_connection` → `from backend.database.db_connection import get_postgres_connection`. Then `Grep neo4j` in the file — planning research found only the import; if any call sites surface, remove them the same way (they are unreachable, Neo4j is down).

`backend/utils/config.py`: remove the four `neo4j_*` fields (lines 52-56 incl. the comment).

`.env` and `.env.example`: delete the whole `# Neo4j Configuration` block (all `NEO4J_*` keys, `DISABLE_NEO4J`) and the `# Graph RAG Settings` block (`GRAPH_RAG_ENABLED`, `GRAPH_CONTEXT_DEPTH`).

- [ ] **Step 7: Clean the frontend's Neo4j sync step**

In `frontend/modules/assistant.py`, replace lines 350-374 (the `try:` block that POSTs to `/api/jobs/sync-to-neo4j` and its logging, ending at the `# Continue with analysis regardless of sync status` comment):

```python
                        try:
                            # First ensure job data is synced to Neo4j
                            try:
                                job_id = selected_job.get('id') if selected_job else None
                                sync_response = None
                                if job_id:
                                    sync_url = f"{get_backend_url()}/api/jobs/sync-to-neo4j"
                                    sync_response = requests.post(
                                        sync_url,
                                        json={"job_ids": [job_id]},
                                        timeout=30
                                    )
                                
                                if sync_response and sync_response.status_code == 200:
                                    logger.info(f"Job successfully synced to Neo4j: {sync_response.json()}")
                                elif sync_response:
                                    logger.warning(f"Job sync warning: {sync_response.text}")
                                else:
                                    logger.warning("No job ID available for sync")
                            except requests.exceptions.Timeout:
                                logger.warning("Job sync timed out, continuing with analysis")
                            except Exception as e:
                                logger.warning(f"Job sync error: {e}, continuing with analysis")
                            
                            # Continue with analysis regardless of sync status
                                
```

with:

```python
                        try:
```

And replace the stale advice at lines 466-469:

```python
                                # If the error is related to Neo4j, try to provide a helpful message
                                error_msg = result.get("message", "").lower()
                                if "neo4j" in error_msg or "graph" in error_msg or "vector" in error_msg or "embedding" in error_msg:
                                    st.warning("⚠️ **Database Synchronization Issue:** Try running the job sync script to ensure all jobs are properly synchronized to the graph database.")
```

with:

```python
                                # Embedding-related failures are non-fatal; analysis proceeds without vectors
                                error_msg = result.get("message", "").lower()
                                if "vector" in error_msg or "embedding" in error_msg:
                                    st.warning("⚠️ Embedding service unavailable — analysis completed without semantic scoring.")
```

- [ ] **Step 8: Repo-wide leftover sweep**

```powershell
poetry run python -c "import backend.main; print('imports clean')"
```

Then grep (excluding docs/documentation/alembic versions):

```powershell
git grep -il neo4j -- backend frontend *.py | Where-Object { $_ -notmatch 'alembic' }
```

Expected: at most `frontend/modules/resume_upload.py` (the word "neo4j" in a list of database skill keywords — that is resume-skill vocabulary, LEAVE IT) and comment-only mentions in `backend/api/routes/job_routes.py`. Fix anything else found.

- [ ] **Step 9: Boot and verify the matching endpoint**

```powershell
poetry run python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

In a second command:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/health
Invoke-RestMethod "http://127.0.0.1:8010/api/jobs/1/matching-candidates?limit=5"
```

Expected: `status: ok`, then a JSON body with `job_id`, `job_title`, and a non-empty `candidates` array with `match_score` values (job id 1 exists; if it doesn't, list ids via `Invoke-RestMethod http://127.0.0.1:8010/api/jobs/`). Stop uvicorn after.

- [ ] **Step 10: Run the suite**

```powershell
poetry run pytest -q 2>&1 | Select-Object -Last 3
```

Expected: **59 passed** (Task 2 added one), 0 failed. If collection errors mention a module importing a deleted file, remove that import the same way as Steps 3-6.

- [ ] **Step 11: Commit**

```powershell
git add -A
git commit -m "refactor: delete the Neo4j layer (graph_service, rag_service, vector shims)"
```

---

### Task 5: Drop the Neo4j/LangChain dependencies

**Files:**
- Modify: `pyproject.toml`, `poetry.lock`

- [ ] **Step 1: Remove the packages**

```powershell
poetry remove neo4j langchain langchain-community langchain-groq rerankers
```

(`rerankers` was used only by the deleted `rag_service._rerank_documents`.)

- [ ] **Step 2: Verify import + suite from the pruned env**

```powershell
poetry run python -c "import backend.main; print('boot imports OK')"
poetry run pytest -q 2>&1 | Select-Object -Last 3
```

Expected: `boot imports OK`; 59 passed, 0 failed. A failure here means some surviving module still imports one of the removed packages at top level — find it with `git grep -l "langchain\|neo4j\|rerankers" -- backend` and fix.

- [ ] **Step 3: Commit**

```powershell
git add pyproject.toml poetry.lock
git commit -m "chore: drop neo4j, langchain*, rerankers dependencies"
```

---

### Task 6: Ollama embedding adapter (768-dim) via ollama.sentienttrader.ai

Replaces the sentence-transformers adapter inside `llm_service.get_embedding_model()`. Same duck-typed surface (`encode` / `embed_query` / `embed_documents`), so `cache_utils.get_embedding_cached`, `intent_processor`, `agent_memory_manager`, and `MatchingEnhancer` all keep working unchanged. Guard rules from spec §4.4: ~20s timeout, never retry against a busy GPU, degrade gracefully.

**Files:**
- Create: `backend/services/ollama_embeddings.py`
- Modify: `backend/utils/config.py` (add 3 fields), `backend/services/llm_service.py` (`get_embedding_model`, delete `_load_sentence_transformer_model`, line 16 env var), `.env.example`
- Test: `backend/tests/test_ollama_embeddings.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ollama_embeddings.py`:

```python
"""OllamaEmbeddingAdapter: 768-dim embeddings over HTTP with graceful offline fallback."""
import numpy as np
import pytest

from backend.services.ollama_embeddings import OllamaEmbeddingAdapter


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def make_adapter(monkeypatch, embeddings=None, fail=False):
    adapter = OllamaEmbeddingAdapter(base_url="http://fake:11434", model="nomic-embed-text")

    def fake_post(url, json=None, timeout=None):
        if fail:
            raise ConnectionError("tunnel down")
        n = len(json["input"])
        vecs = embeddings or [[0.1] * 768 for _ in range(n)]
        return FakeResponse({"embeddings": vecs})

    monkeypatch.setattr(adapter._client, "post", fake_post)
    return adapter


def test_embed_query_returns_768_list(monkeypatch):
    adapter = make_adapter(monkeypatch)
    vec = adapter.embed_query("data engineer with airflow")
    assert isinstance(vec, list)
    assert len(vec) == 768


def test_embed_documents_batches(monkeypatch):
    adapter = make_adapter(monkeypatch)
    vecs = adapter.embed_documents(["a", "b", "c"])
    assert len(vecs) == 3 and all(len(v) == 768 for v in vecs)


def test_encode_single_returns_ndarray(monkeypatch):
    adapter = make_adapter(monkeypatch)
    out = adapter.encode("hello")
    assert isinstance(out, np.ndarray) and out.shape == (768,)


def test_encode_list_returns_2d_ndarray(monkeypatch):
    adapter = make_adapter(monkeypatch)
    out = adapter.encode(["hello", "world"])
    assert isinstance(out, np.ndarray) and out.shape == (2, 768)


def test_offline_fallback_is_deterministic_768(monkeypatch):
    adapter = make_adapter(monkeypatch, fail=True)
    v1 = adapter.embed_query("same text")
    v2 = adapter.embed_query("same text")
    v3 = adapter.embed_query("different text")
    assert len(v1) == 768
    assert v1 == v2, "fallback must be deterministic for caching"
    assert v1 != v3
```

- [ ] **Step 2: Run — expect import error**

```powershell
poetry run pytest backend/tests/test_ollama_embeddings.py -v
```

Expected: FAIL — `ModuleNotFoundError: backend.services.ollama_embeddings`.

- [ ] **Step 3: Implement the adapter**

Create `backend/services/ollama_embeddings.py`:

```python
"""768-dim embeddings from the existing Ollama endpoint (nomic-embed-text).

Replaces the sentence-transformers (384-dim, PyTorch) adapter. Design rules
from the revival spec §4.2/§4.4: best-effort with a hard timeout, no retries
against a possibly-busy GPU, deterministic local fallback so cached scores
stay stable when the tunnel is down.
"""
import hashlib
import logging
from typing import List, Union

import httpx
import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768


class OllamaEmbeddingAdapter:
    """Duck-type compatible with the old SentenceTransformerAdapter:
    encode() -> np.ndarray, embed_query() -> list, embed_documents() -> list[list]."""

    def __init__(self, base_url: str, model: str = "nomic-embed-text", timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=timeout)
        self._warned_offline = False

    def _fallback(self, text: str) -> List[float]:
        # Deterministic pseudo-embedding: stable across calls so Redis-cached
        # scores don't jitter while the tunnel is down. Not semantically useful.
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        return rng.standard_normal(EMBEDDING_DIM).tolist()

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            resp = self._client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
            )
            resp.raise_for_status()
            embeddings = resp.json()["embeddings"]
            if len(embeddings) != len(texts) or any(len(e) != EMBEDDING_DIM for e in embeddings):
                raise ValueError(
                    f"expected {len(texts)}x{EMBEDDING_DIM} embeddings, got "
                    f"{len(embeddings)}x{len(embeddings[0]) if embeddings else 0}"
                )
            self._warned_offline = False
            return embeddings
        except Exception as e:
            if not self._warned_offline:
                logger.warning(f"Ollama embeddings unavailable ({e}); using deterministic fallback")
                self._warned_offline = True
            return [self._fallback(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_batch([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed_batch(list(texts))

    def encode(self, text: Union[str, List[str]]) -> np.ndarray:
        """cache_utils.get_embedding_cached calls this in a thread pool."""
        if isinstance(text, str):
            return np.array(self._embed_batch([text])[0])
        return np.array(self._embed_batch(list(text)))
```

- [ ] **Step 4: Run the tests — expect pass**

```powershell
poetry run pytest backend/tests/test_ollama_embeddings.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Add settings**

In `backend/utils/config.py`, where the Neo4j block used to be (after `postgres_conn`), add:

```python
    # Embeddings (Ollama over the existing Cloudflare tunnel; spec §4.2)
    ollama_base_url: str = Field(default=os.getenv("OLLAMA_BASE_URL", "https://ollama.sentienttrader.ai"))
    ollama_embed_model: str = Field(default=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"))
    ollama_embed_timeout: float = Field(default=float(os.getenv("OLLAMA_EMBED_TIMEOUT", "20.0")))
```

- [ ] **Step 6: Swap `get_embedding_model` internals**

In `backend/services/llm_service.py`:
- Delete line 16: `os.environ['SENTENCE_TRANSFORMERS_HOME'] = './models/sentence_transformers'`
- Delete the whole `_load_sentence_transformer_model` function (lines ~174-190).
- Replace the whole `get_embedding_model` method (lines ~280-336, both inner adapter classes included) with:

```python
    def get_embedding_model(self):
        """Return the shared 768-dim Ollama embedding adapter (loaded once)."""
        if not self._embedding_model_loaded:
            from backend.services.ollama_embeddings import OllamaEmbeddingAdapter
            self.embedding_model = OllamaEmbeddingAdapter(
                base_url=getattr(self.settings, "ollama_base_url", "https://ollama.sentienttrader.ai"),
                model=getattr(self.settings, "ollama_embed_model", "nomic-embed-text"),
                timeout=getattr(self.settings, "ollama_embed_timeout", 20.0),
            )
            self._embedding_model_loaded = True
        return self.embedding_model
```

- [ ] **Step 7: Update `.env.example`** — add under the database section:

```
# Embeddings — served by an existing Ollama instance (see README)
OLLAMA_BASE_URL=https://ollama.sentienttrader.ai
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_EMBED_TIMEOUT=20.0
```

- [ ] **Step 8: Live smoke test (tunnel must be up) + suite**

```powershell
poetry run python -c "from backend.services.ollama_embeddings import OllamaEmbeddingAdapter; a=OllamaEmbeddingAdapter('https://ollama.sentienttrader.ai'); v=a.embed_query('senior data engineer'); print('live dims:', len(v))"
poetry run pytest -q 2>&1 | Select-Object -Last 3
```

Expected: `live dims: 768` (if the tunnel is down you'll get the fallback warning — still 768; note it and move on), suite 64 passed (59 + 5 new), 0 failed.

- [ ] **Step 9: Commit**

```powershell
git add backend/services/ollama_embeddings.py backend/services/llm_service.py backend/utils/config.py backend/tests/test_ollama_embeddings.py .env.example
git commit -m "feat: 768-dim embeddings via ollama nomic-embed-text, replacing sentence-transformers"
```

---

### Task 7: Drop the PyTorch stack

Spec §4.2: "No PyTorch anywhere." OCR keeps working through pytesseract (`ocr_processor.py` treats easyocr as one optional engine with a warning fallback). spaCy stays — it is not PyTorch and the NLP extractors import it at module top level.

**Files:**
- Modify: `pyproject.toml`, `poetry.lock`

- [ ] **Step 1: Remove the packages**

```powershell
poetry remove sentence-transformers transformers torch-directml easyocr
```

If poetry reports one of them as a required transitive dependency of something kept, stop and report which — do not force.

- [ ] **Step 2: Verify OCR degrades gracefully and suite is green**

```powershell
poetry run python -c "import backend.main; print('boot imports OK')"
poetry run pytest -q 2>&1 | Select-Object -Last 3
```

Expected: `boot imports OK`; 64 passed, 0 failed. (The ocr_processor 'easyocr not available' warning during tests is expected and fine.)

- [ ] **Step 3: Measure the cold-start win**

```powershell
poetry run python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

then time the previously-28s endpoint:

```powershell
Measure-Command { Invoke-RestMethod "http://127.0.0.1:8010/api/candidates" } | Select-Object TotalSeconds
```

Expected: dramatically under 28 s cold (the lazy PyTorch loads are gone). Record the number — it's a README bullet. Stop uvicorn.

- [ ] **Step 4: Commit**

```powershell
git add pyproject.toml poetry.lock
git commit -m "chore: drop sentence-transformers, transformers, torch-directml, easyocr (no PyTorch anywhere)"
```

---

### Task 8: Docker Compose — pgvector Postgres + Redis, and migrate the dev DB into it

**USER STEP FIRST (Sean):** Install Docker Desktop for Windows from https://www.docker.com/products/docker-desktop/ — choose the **WSL 2 backend** during install (your WSL Ubuntu already exists, so no extra setup). After install, start Docker Desktop once and verify `docker --version` works in a terminal. Everything after this is scripted.

Design: container Postgres maps to host port **5433** (the Windows service on 5432 keeps serving CollinsAI, untouched). Compose Redis maps to **6380** and is optional locally — `.env` keeps pointing at the WSL Redis on 6379; the compose Redis exists so a fresh clone needs nothing outside Docker. A backend Dockerfile is deliberately **deferred to Phase 4** (deploy) — the compose file here is the data layer.

**Files:**
- Create: `docker-compose.yml`
- Modify: `.env` (`POSTGRES_CONN` port + `POSTGRES_PORT`), `.env.example`

- [ ] **Step 1: Write `docker-compose.yml`** (repo root):

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: recruitiq-db
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set in .env}
      POSTGRES_DB: ats_db
    ports:
      - "5433:5432"   # 5432 on the host belongs to the pre-existing Windows Postgres service
    volumes:
      - recruitiq_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin -d ats_db"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: recruitiq-redis
    ports:
      - "6380:6379"   # 6379 on the host is WSL Redis; fresh clones can point REDIS_URL at 6380

volumes:
  recruitiq_pgdata:
```

- [ ] **Step 2: Start it**

```powershell
docker compose up -d db
docker compose ps
```

Expected: `recruitiq-db` state `running (healthy)`.

- [ ] **Step 3: Copy the live database into the container**

Dump from the Windows service (5432) and restore into the container (5433). The password is in `.env` (`POSTGRES_PASSWORD`); both sides use the same value because compose read it from `.env`:

```powershell
$pw = (Get-Content .env | Select-String '^POSTGRES_PASSWORD=').ToString().Split('=')[1].Trim('"')
$env:PGPASSWORD = $pw
pg_dump -U admin -h localhost -p 5432 -d ats_db -F c -f ats_db_migration.dump
pg_restore -U admin -h localhost -p 5433 -d ats_db --no-owner ats_db_migration.dump
psql -U admin -h localhost -p 5433 -d ats_db -c "SELECT (SELECT count(*) FROM candidates) AS candidates, (SELECT count(*) FROM jobs) AS jobs, (SELECT count(*) FROM resumes) AS resumes;"
```

Expected: counts matching the live DB (23 candidates / 6 jobs / 30 resumes as of planning). `pg_restore` may print harmless "extension pg_trgm already exists"-class warnings. Delete the dump file after: `Remove-Item ats_db_migration.dump`.

- [ ] **Step 4: Verify pgvector is available in the container**

```powershell
psql -U admin -h localhost -p 5433 -d ats_db -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extversion FROM pg_extension WHERE extname='vector';"
```

Expected: a version row (0.7+).

- [ ] **Step 5: Point the app at the container**

In `.env`: change `POSTGRES_CONN` port `5432` → `5433` and `POSTGRES_PORT` to `5433`. In `.env.example`: same port change on `POSTGRES_CONN`, plus a comment `# 5433 = the docker-compose pgvector Postgres`.

- [ ] **Step 6: Verify Alembic and the app against the container**

```powershell
poetry run alembic -c backend/alembic.ini current
poetry run pytest -q 2>&1 | Select-Object -Last 3
```

Expected: `716ed00c4df0 (head)` (alembic_version came over in the dump); suite 64 passed. Boot check:

```powershell
poetry run python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
Invoke-RestMethod "http://127.0.0.1:8010/api/jobs/" | Select-Object total
```

Expected: `total: 6`. Stop uvicorn.

- [ ] **Step 7: Commit**

```powershell
git add docker-compose.yml .env.example
git commit -m "feat: docker-compose with pgvector Postgres (5433) and Redis; dev DB migrated into container"
```

---

### Task 9: Alembic migration — vector extension, 768-dim columns, HNSW indexes

`agent_memories` exists in models at `Vector(384)` but in no real database (live DB lacked pgvector). Now that the dev DB has pgvector: move the model to 768 and create everything at 768. The migration drops any stray 384-dim `agent_memories` (it is empty everywhere) before recreating.

**Files:**
- Modify: `backend/models/models.py` (AgentMemory line 372; add Job.embedding, Candidate.embedding)
- Create: `backend/alembic/versions/<generated>_pgvector_768_embeddings.py`

- [ ] **Step 1: Update the models**

In `backend/models/models.py`:
- Line 372: `embedding = Column(Vector(384))` → `embedding = Column(Vector(768))  # nomic-embed-text` (update the trailing comment if it names all-MiniLM).
- In the `Job` model, add alongside its other columns:

```python
    embedding = Column(Vector(768), nullable=True)  # nomic-embed-text over title+overview+quals+skills
```

- In the `Candidate` model, add:

```python
    embedding = Column(Vector(768), nullable=True)  # nomic-embed-text over position+skills
```

- [ ] **Step 2: Write the migration**

```powershell
poetry run alembic -c backend/alembic.ini revision -m "pgvector 768 embeddings"
```

Fill the generated file:

```python
"""pgvector 768 embeddings

Revision ID: <keep generated>
Revises: 716ed00c4df0
Create Date: <keep generated>
"""
import sqlalchemy as sa
import pgvector.sqlalchemy
from alembic import op

revision = "<keep generated>"
down_revision = "716ed00c4df0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # agent_memories was 384-dim in the baseline and only created where pgvector
    # existed — i.e. nowhere real. Recreate at 768 unconditionally.
    op.execute("DROP TABLE IF EXISTS agent_memories")
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), index=True),
        sa.Column("agent_name", sa.String(length=100), index=True),
        sa.Column("memory_type", sa.String(length=50)),
        sa.Column("content", sa.JSON()),
        sa.Column("importance", sa.Float()),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=768)),
        sa.Column("created_at", sa.DateTime()),
    )

    op.add_column("jobs", sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=768), nullable=True))
    op.add_column("candidates", sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=768), nullable=True))

    op.execute("CREATE INDEX ix_jobs_embedding_hnsw ON jobs USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX ix_candidates_embedding_hnsw ON candidates USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_candidates_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_jobs_embedding_hnsw")
    op.drop_column("candidates", "embedding")
    op.drop_column("jobs", "embedding")
    op.execute("DROP TABLE IF EXISTS agent_memories")
```

**IMPORTANT:** copy the column list for `agent_memories` from the baseline migration `backend/alembic/versions/716ed00c4df0_*.py` (search for `agent_memories` there) rather than trusting the list above — match names/types exactly except `Vector(dim=768)`.

- [ ] **Step 3: Run and verify**

```powershell
poetry run alembic -c backend/alembic.ini upgrade head
$pw = (Get-Content .env | Select-String '^POSTGRES_PASSWORD=').ToString().Split('=')[1].Trim('"'); $env:PGPASSWORD = $pw
psql -U admin -h localhost -p 5433 -d ats_db -c "\d jobs" 
psql -U admin -h localhost -p 5433 -d ats_db -c "\d agent_memories"
```

Expected: `embedding | vector(768)` on jobs (plus the hnsw index listed), and agent_memories exists with `vector(768)`.

- [ ] **Step 4: Downgrade/upgrade round-trip (proves reversibility)**

```powershell
poetry run alembic -c backend/alembic.ini downgrade 716ed00c4df0
poetry run alembic -c backend/alembic.ini upgrade head
```

Expected: both succeed.

- [ ] **Step 5: Suite, then commit**

```powershell
poetry run pytest -q 2>&1 | Select-Object -Last 3
git add backend/models/models.py backend/alembic/versions/
git commit -m "feat: pgvector migration - 768-dim embeddings on jobs, candidates, agent_memories"
```

---

### Task 10: Store embeddings in pgvector + similarity search

Rebuilds the two methods stubbed in Task 4 and backfills the existing rows. One embedding per job/candidate (single 768 vector over concatenated text) — simpler and more useful than the old three-vectors-per-job Neo4j scheme.

**Files:**
- Create: `backend/services/vector_search_service.py`, `scripts/backfill_embeddings.py`
- Modify: `backend/services/job_service.py` (the two Task-4 stubs)
- Test: `backend/tests/test_vector_search.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_vector_search.py`:

```python
"""pgvector-backed embedding storage and similarity search (DB-integration)."""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

POSTGRES_CONN = os.getenv("POSTGRES_CONN", "").strip('"')


def _pgvector_available():
    if not POSTGRES_CONN:
        return False
    try:
        engine = create_engine(POSTGRES_CONN)
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname='vector'")
            ).scalar() > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _pgvector_available(), reason="needs Postgres with pgvector")


class StubEmbedder:
    """Deterministic 768-dim embeddings; nearby texts share a prefix dimension."""

    def embed_query(self, txt):
        base = [0.0] * 768
        base[0] = 1.0 if "python" in txt.lower() else -1.0
        base[1] = len(txt) % 7 / 7.0
        return base

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]


@pytest.fixture
def db():
    engine = create_engine(POSTGRES_CONN)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def test_store_and_search_similar_jobs(db):
    from backend.models.models import Job
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(embedding_model=StubEmbedder())

    jobs = db.query(Job).limit(3).all()
    assert len(jobs) >= 2, "test DB must contain at least 2 jobs"

    for job in jobs:
        assert svc.store_job_embedding(db, job.id) is True

    results = svc.find_similar_jobs(db, jobs[0].id, limit=5)
    assert isinstance(results, list) and len(results) >= 1
    assert all(r["id"] != jobs[0].id for r in results), "must exclude the query job"
    assert all(0.0 <= r["similarity"] <= 1.0 for r in results)


def test_store_candidate_embedding(db):
    from backend.models.models import Candidate
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(embedding_model=StubEmbedder())
    candidate = db.query(Candidate).first()
    assert candidate is not None
    assert svc.store_candidate_embedding(db, candidate.id) is True

    row = db.execute(
        __import__("sqlalchemy").text("SELECT embedding IS NOT NULL FROM candidates WHERE id = :cid"),
        {"cid": candidate.id},
    ).scalar()
    assert row is True


def test_search_candidates_by_text(db):
    """Natural-language semantic candidate search over pgvector (the RAG-showcase path)."""
    from backend.models.models import Candidate
    from backend.services.vector_search_service import VectorSearchService

    svc = VectorSearchService(embedding_model=StubEmbedder())
    candidates = db.query(Candidate).limit(3).all()
    if not candidates:
        pytest.skip("needs seeded candidates")
    for c in candidates:
        svc.store_candidate_embedding(db, c.id)

    results = svc.search_candidates_by_text(db, "python data engineer with airflow", limit=5)
    assert isinstance(results, list) and len(results) >= 1
    assert all({"id", "name", "position", "similarity"} <= set(r) for r in results)
    sims = [r["similarity"] for r in results]
    assert sims == sorted(sims, reverse=True), "must be ranked best-first"
```

- [ ] **Step 2: Run — expect import error**

```powershell
poetry run pytest backend/tests/test_vector_search.py -v
```

Expected: FAIL (`vector_search_service` doesn't exist). If it SKIPS, `POSTGRES_CONN` isn't set in the shell — pytest loads `.env`? It does not automatically; run with `$env:POSTGRES_CONN` set from `.env` first (same `Select-String` pattern as Task 8 Step 3, key `POSTGRES_CONN`).

- [ ] **Step 3: Implement the service**

Create `backend/services/vector_search_service.py`:

```python
"""pgvector-backed embedding storage and cosine similarity search.

Replaces the deleted Neo4j graph_service vector layer (Phase 1b). One 768-dim
vector per job/candidate, computed from concatenated descriptive text.
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _job_text(job) -> str:
    skills = job.skills or ""
    if isinstance(skills, list):
        skills = ", ".join(skills)
    return " | ".join(
        p for p in [job.title, job.job_overview, job.required_qualifications, skills] if p
    )


def _candidate_text(candidate) -> str:
    skills = ""
    if getattr(candidate, "skills", None):
        skills = ", ".join(s.skill_name for s in candidate.skills)
    return " | ".join(p for p in [candidate.current_position, skills] if p)


class VectorSearchService:
    def __init__(self, embedding_model):
        self.embedding_model = embedding_model

    def store_job_embedding(self, db, job_id: int) -> bool:
        from backend.models.models import Job

        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning(f"store_job_embedding: job {job_id} not found")
            return False
        content = _job_text(job)
        if not content:
            return False
        job.embedding = self.embedding_model.embed_query(content)
        db.commit()
        return True

    def store_candidate_embedding(self, db, candidate_id: str) -> bool:
        from backend.models.models import Candidate

        candidate = db.query(Candidate).filter(Candidate.id == str(candidate_id)).first()
        if not candidate:
            logger.warning(f"store_candidate_embedding: candidate {candidate_id} not found")
            return False
        content = _candidate_text(candidate)
        if not content:
            return False
        candidate.embedding = self.embedding_model.embed_query(content)
        db.commit()
        return True

    def search_candidates_by_text(self, db, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Semantic candidate search: embed the natural-language query, cosine-rank
        candidates. This is the pgvector successor to the old (non-functional)
        Neo4j RAG retrieval; Phase 2's search_candidates tool will call it."""
        query_vec = self.embedding_model.embed_query(query)
        rows = db.execute(
            text(
                """
                SELECT c.id, c.first_name, c.last_name, c.email, c.current_position,
                       1 - (c.embedding <=> CAST(:qvec AS vector)) AS similarity
                FROM candidates c
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> CAST(:qvec AS vector)
                LIMIT :limit
                """
            ),
            {"qvec": str(query_vec), "limit": limit},
        ).fetchall()
        return [
            {
                "id": r.id,
                "name": f"{r.first_name or ''} {r.last_name or ''}".strip(),
                "email": r.email,
                "position": r.current_position,
                "similarity": max(0.0, min(1.0, float(r.similarity))),
            }
            for r in rows
        ]

    def find_similar_jobs(self, db, job_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Cosine similarity over jobs.embedding; excludes the query job."""
        rows = db.execute(
            text(
                """
                SELECT j.id, j.title, j.department, j.location,
                       1 - (j.embedding <=> q.embedding) AS similarity
                FROM jobs j, jobs q
                WHERE q.id = :job_id
                  AND j.id != :job_id
                  AND j.embedding IS NOT NULL
                  AND q.embedding IS NOT NULL
                ORDER BY j.embedding <=> q.embedding
                LIMIT :limit
                """
            ),
            {"job_id": job_id, "limit": limit},
        ).fetchall()
        return [
            {"id": r.id, "title": r.title, "department": r.department,
             "location": r.location, "similarity": max(0.0, min(1.0, float(r.similarity)))}
            for r in rows
        ]
```

- [ ] **Step 4: Run the tests — expect pass**

```powershell
poetry run pytest backend/tests/test_vector_search.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Replace the two Task-4 stubs in job_service**

In `backend/services/job_service.py`, replace the Task-4 `store_job_embeddings` stub with:

```python
    def store_job_embeddings(self, db, job_id: int) -> bool:
        """Store a 768-dim pgvector embedding for the job (Phase 1b)."""
        if not self.llm_service:
            return False
        from backend.services.vector_search_service import VectorSearchService
        svc = VectorSearchService(embedding_model=self.llm_service.get_embedding_model())
        return svc.store_job_embedding(db, job_id)
```

and rewire the similar-jobs method stubbed in Task 4 to call `VectorSearchService.find_similar_jobs` — preserve its original signature and returned shape (read the pre-Task-4 version in git history: `git show HEAD~6:backend/services/job_service.py` and match the fields callers consume; the caller is in `intent_processor.py`).

- [ ] **Step 6: Backfill script**

Create `scripts/backfill_embeddings.py`:

```python
"""One-shot: embed every job and candidate into pgvector via the Ollama endpoint.

Usage:  poetry run python scripts/backfill_embeddings.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.models import Candidate, Job
from backend.services.ollama_embeddings import OllamaEmbeddingAdapter
from backend.services.vector_search_service import VectorSearchService


def main():
    engine = create_engine(os.environ["POSTGRES_CONN"].strip('"'))
    session = sessionmaker(bind=engine)()
    svc = VectorSearchService(
        embedding_model=OllamaEmbeddingAdapter(
            base_url=os.getenv("OLLAMA_BASE_URL", "https://ollama.sentienttrader.ai")
        )
    )

    jobs = session.query(Job.id).all()
    ok = sum(svc.store_job_embedding(session, j.id) for j in jobs)
    print(f"jobs embedded: {ok}/{len(jobs)}")

    candidates = session.query(Candidate.id).all()
    ok = sum(svc.store_candidate_embedding(session, c.id) for c in candidates)
    print(f"candidates embedded: {ok}/{len(candidates)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run the backfill (tunnel up)**

```powershell
poetry run python scripts/backfill_embeddings.py
```

Expected: `jobs embedded: 6/6`, `candidates embedded: N/23` (N < 23 is fine — candidates with no position AND no skills have no text to embed; the script prints the ratio honestly). Verify no fallback warnings in the output — if the tunnel was down, embeddings are deterministic noise; rerun when it's up.

- [ ] **Step 8: Full suite + commit**

```powershell
poetry run pytest -q 2>&1 | Select-Object -Last 3
git add backend/services/vector_search_service.py backend/services/job_service.py scripts/backfill_embeddings.py backend/tests/test_vector_search.py
git commit -m "feat: pgvector embedding storage, cosine similar-jobs search, backfill script"
```

---

### Task 11: GitHub Actions CI

Gate: ruff (error-class rules only — the legacy code cannot pass the full style gate yet) + pytest against a pgvector service container. Network-dependent and data-dependent tests must skip cleanly in CI.

**Files:**
- Create: `.github/workflows/ci.yml`
- Possibly modify: individual tests that assume live data (add skip guards)

- [ ] **Step 1: Dry-run the CI conditions locally**

Simulate an empty-schema DB to find data-dependent tests:

```powershell
$pw = (Get-Content .env | Select-String '^POSTGRES_PASSWORD=').ToString().Split('=')[1].Trim('"'); $env:PGPASSWORD = $pw
psql -U admin -h localhost -p 5433 -c "DROP DATABASE IF EXISTS ats_ci; CREATE DATABASE ats_ci;"
$env:POSTGRES_CONN = "postgresql://admin:$pw@localhost:5433/ats_ci"
poetry run alembic -c backend/alembic.ini upgrade head
poetry run pytest -q 2>&1 | Select-Object -Last 10
```

Any test that fails only because tables are empty (e.g. `test_vector_search.py` asserts ≥2 jobs) gets a skip guard, e.g. change that assert to:

```python
    if len(jobs) < 2:
        pytest.skip("needs seeded jobs")
```

Iterate until the run is green (passes+skips, 0 failures) against the empty DB. Then restore `$env:POSTGRES_CONN` (or just open a fresh shell) and drop `ats_ci`:

```powershell
psql -U admin -h localhost -p 5433 -c "DROP DATABASE ats_ci;"
```

- [ ] **Step 2: Check the lint gate locally**

```powershell
poetry run ruff check backend --select E9,F63,F7,F82 --exclude backend/tests
```

Expected: clean (these rules are syntax errors / undefined names only). Fix anything real it finds — an undefined name in a surviving module is a genuine leftover from Task 4.

- [ ] **Step 3: Write the workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: ci
          POSTGRES_PASSWORD: ci
          POSTGRES_DB: ats_ci
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U ci"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10

    env:
      POSTGRES_CONN: postgresql://ci:ci@localhost:5432/ats_ci
      OLLAMA_BASE_URL: http://localhost:1  # unreachable on purpose: embedding fallback path in CI

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Poetry
        run: pipx install poetry

      - uses: actions/cache@v4
        with:
          path: ~/.cache/pypoetry
          key: poetry-${{ runner.os }}-${{ hashFiles('poetry.lock') }}

      - name: Install dependencies
        run: poetry install --no-interaction

      - name: Lint (error-class rules)
        run: poetry run ruff check backend --select E9,F63,F7,F82 --exclude backend/tests

      - name: Migrate schema
        run: poetry run alembic -c backend/alembic.ini upgrade head

      - name: Test
        run: poetry run pytest -q
```

- [ ] **Step 4: Commit and watch the first run**

```powershell
git add .github/workflows/ci.yml
git add -A   # any skip guards added in Step 1
git commit -m "ci: GitHub Actions - ruff error gate + pytest against pgvector service"
git push -u origin phase-1b-pgvector
gh run watch
```

Expected: green. Iterate on failures (most likely: a system package a test needs, e.g. tesseract — the correct fix is a skip guard, not installing OCR in CI).

---

### Task 12: Docs, final gate, merge

**Files:**
- Modify: `README.md`, `TESTING.md`, `.env.example`, this plan (check boxes)

- [ ] **Step 1: Update README.md**

- Data layer section: single Postgres + pgvector; Neo4j fully removed (say why in one sentence: non-functional vector layer, biggest setup barrier).
- Quick start: `docker compose up -d db`, `poetry install`, `poetry run alembic -c backend/alembic.ini upgrade head`, uvicorn on 8010. Remove any Neo4j/LangChain mentions.
- Headline numbers (verify each before writing): ~3,100 lines deleted this phase (`git diff main --shortstat` for the real number), LangChain and the PyTorch stack gone from dependencies (count removed packages: 9), `/api/candidates` cold start from 28 s → the Task 7 measured number, embeddings 384→768-dim via existing Ollama infrastructure.

- [ ] **Step 2: Update TESTING.md** with the real final counts from a fresh `poetry run pytest -q`.

- [ ] **Step 3: Final gate — run each, record output**

```powershell
git status                                            # clean
poetry run pytest -q 2>&1 | Select-Object -Last 3     # 0 failed
poetry run python -c "import backend.main; from backend.main import app; print('routes:', len(app.routes))"   # 92
git grep -il "langchain" -- backend | Measure-Object  # 0 (text_splitter.py docstring mention is fine if it remains — decide: reword it)
# password-absence check: grep tracked files for the old DB password stem
# (write the stem yourself from .env history - never commit it in a doc)
git grep -c "<old-password-stem>" -- . ':!docs'       # expect: nothing
docker compose ps                                     # db healthy
```

Boot + endpoints:

```powershell
poetry run python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
Invoke-RestMethod http://127.0.0.1:8010/health
Invoke-RestMethod "http://127.0.0.1:8010/api/jobs/1/matching-candidates?limit=5"
```

Both 200 with real data. Stop uvicorn.

- [ ] **Step 4: Commit docs, then merge ceremony**

```powershell
git add README.md TESTING.md docs/
git commit -m "docs: Phase 1b results - pgvector migration, dependency diet, compose, CI"
```

Then use **superpowers:finishing-a-development-branch** — merge to main, push, verify CI green on main, delete the branch.

---

## Execution notes

- **Order matters:** Tasks 2-7 run against the current DB and require no Docker. Task 8 is the first one needing Docker Desktop installed (user step). If Docker install is blocked, Tasks 2-7 still merge cleanly as "Phase 1b part 1".
- **Suite count arithmetic:** 58 baseline → +1 (Task 2) → +5 (Task 6) → +3 DB tests (Task 10, skip without pgvector) = 67 expected passes locally by the end; CI will show more skips (no seed data, no tunnel).
- **The tunnel being down** never blocks execution: the adapter falls back deterministically. It only blocks the *backfill* being semantically meaningful (Task 10 Step 7 — rerun when up).
- **Do not** touch `regex_extractor.py`'s shadowed duplicate methods, `intent_processor.py`'s size, or `assistant.py`'s 3,135 lines — that is Phase 2 (tool calling) scope.
