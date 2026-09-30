"""The assistant must say when data is not there instead of inventing it.

Regression net for the 2026-09-30 assistant audit (F1, F2, F5): salary
benchmarks without a search backend, job titles the ATS does not have, and
searches run while the embedding service is down. Everything here runs
without Postgres or an LLM; the DB-backed variants live in
test_assistant_tools_db.py.
"""
import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services.assistant_tools import (
    MIN_JOB_LOOKUP_RELEVANCE,
    SALARY_UNAVAILABLE_NOTE,
    SEARCH_DEGRADED_NOTE,
    build_assistant_tools,
)
from backend.services.market_research_service import MarketResearchService

REPO = Path(__file__).resolve().parents[2]


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _NoSearch:
    has_backend = False

    async def search(self, query, max_results=5):
        raise AssertionError("search must not run without a backend")


class _EmptySearch:
    has_backend = True

    async def search(self, query, max_results=5):
        return []


class _LLMThatMustNotRun:
    def __init__(self):
        self.calls = 0

    async def generate_text_async(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("the analysis LLM must never see empty market data")


class TestSalaryWithoutData:
    def test_no_search_backend_is_unavailable_not_analyzed(self):
        llm = _LLMThatMustNotRun()
        service = MarketResearchService(_NoSearch(), llm)
        result = run(service.get_comprehensive_salary_benchmark("Data Engineer", "Austin, TX"))
        assert result["status"] == "unavailable"
        assert "not available" in result["message"]
        assert llm.calls == 0

    def test_empty_search_results_are_unavailable_not_analyzed(self):
        llm = _LLMThatMustNotRun()
        service = MarketResearchService(_EmptySearch(), llm)
        result = run(service.get_comprehensive_salary_benchmark("Data Engineer", "Austin, TX"))
        assert result["status"] == "unavailable"
        assert "no salary results" in result["reason"]
        assert llm.calls == 0

    def test_metadata_never_claims_real_time(self):
        service = MarketResearchService(_EmptySearch(), _LLMThatMustNotRun())
        enhanced = service._enhance_analysis_data({"salary_benchmarks": {}}, "Austin, TX")
        assert "data_freshness" not in enhanced["metadata"]


class _Registry:
    """Just enough of the service registry for the tool closures."""

    def __init__(self, embedding_model, market=None):
        self.llm_service = SimpleNamespace(get_embedding_model=lambda: embedding_model)
        self.market_research_service = market


class _FakeJobQuery:
    """db.query(Job) that answers filter().first() with None and the listing
    with a fixed set of open jobs, so get_job reaches the semantic branch."""

    def __init__(self, jobs):
        self._jobs = jobs

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def first(self):
        return None

    def all(self):
        return self._jobs


def _tools(monkeypatch, embedding_model, hits, market=None, jobs=None):
    from backend.services import assistant_tools, vector_search_service
    from backend.services import service_registry

    registry = _Registry(embedding_model, market=market)
    monkeypatch.setattr(service_registry, "get_registry", lambda: registry)
    monkeypatch.setattr(
        vector_search_service.VectorSearchService,
        "search_jobs_by_text",
        lambda self, db, query, limit=8: hits,
    )
    monkeypatch.setattr(
        vector_search_service.VectorSearchService,
        "search_candidates_by_text",
        lambda self, db, query, limit=10, location=None, min_similarity=0.0: [],
    )
    jobs = jobs or [
        SimpleNamespace(id=1, title="Data Engineer", status="open"),
        SimpleNamespace(id=2, title="Product Manager", status="open"),
    ]
    db = SimpleNamespace(query=lambda model: _FakeJobQuery(jobs))
    return {t.name: t for t in assistant_tools.build_assistant_tools(db)}


HEALTHY = SimpleNamespace(is_degraded=False)
DEGRADED = SimpleNamespace(is_degraded=True)


class TestUnknownJob:
    def test_below_floor_lists_real_jobs_instead_of_substituting(self, monkeypatch):
        nearest = {"id": 19, "title": "Senior Data Scientist", "similarity": MIN_JOB_LOOKUP_RELEVANCE - 0.05}
        tools = _tools(monkeypatch, HEALTHY, hits=[nearest])
        result = run(tools["get_job"].run(job="Chief Happiness Officer"))
        assert "error" in result and "id" not in result
        assert [j["title"] for j in result["open_jobs"]] == ["Data Engineer", "Product Manager"]
        assert "Chief Happiness Officer" in result["note"]

    def test_match_to_job_refuses_unknown_job(self, monkeypatch):
        nearest = {"id": 19, "title": "Senior Data Scientist", "similarity": 0.1}
        tools = _tools(monkeypatch, HEALTHY, hits=[nearest])
        result = run(tools["match_to_job"].run(job="Chief Happiness Officer"))
        assert "error" in result and "matches" not in result
        assert result["open_jobs"]

    def test_degraded_embeddings_never_resolve_a_title(self, monkeypatch):
        # With a placeholder query vector the "nearest" job is noise even if
        # its similarity happens to clear the floor.
        nearest = {"id": 19, "title": "Senior Data Scientist", "similarity": 0.99}
        tools = _tools(monkeypatch, DEGRADED, hits=[nearest])
        result = run(tools["get_job"].run(job="the ML role"))
        assert "error" in result
        assert result["search_degraded"] is True

    def test_floor_is_in_the_measured_gap(self):
        # Paraphrases of real titles scored 0.60+, titles the ATS lacks 0.54
        # and below (see the constant's comment). Moving the floor outside
        # that gap silently reintroduces substitution or breaks paraphrases.
        assert 0.55 <= MIN_JOB_LOOKUP_RELEVANCE <= 0.60


class TestDegradedSearch:
    def test_search_says_unavailable_not_nobody_matches(self, monkeypatch):
        tools = _tools(monkeypatch, DEGRADED, hits=[])
        result = run(tools["search_candidates"].run(query="python engineer", location="Seattle"))
        assert result["search_degraded"] is True
        assert result["candidates"] == [] and result["count"] == 0
        assert "candidates_elsewhere" not in result
        assert result["note"] == SEARCH_DEGRADED_NOTE

    def test_healthy_search_carries_no_degraded_flag(self, monkeypatch):
        tools = _tools(monkeypatch, HEALTHY, hits=[])
        result = run(tools["search_candidates"].run(query="python engineer"))
        assert "search_degraded" not in result


class TestSalaryTool:
    def test_unavailable_benchmark_becomes_an_explicit_note(self, monkeypatch):
        class _Market:
            async def get_comprehensive_salary_benchmark(self, role, location, level=None):
                return {"status": "unavailable", "reason": "no web search backend is configured"}

        tools = _tools(monkeypatch, HEALTHY, hits=[], market=_Market())
        result = run(tools["get_market_data"].run(role="Data Engineer", location="Austin"))
        assert result["status"] == "unavailable"
        assert result["note"] == SALARY_UNAVAILABLE_NOTE
        assert "salary_benchmarks" not in result

    def test_success_passes_through(self, monkeypatch):
        class _Market:
            async def get_comprehensive_salary_benchmark(self, role, location, level=None):
                return {"status": "success", "data": {"salary_benchmarks": {"mid_level": {}}}}

        tools = _tools(monkeypatch, HEALTHY, hits=[], market=_Market())
        result = run(tools["get_market_data"].run(role="Data Engineer", location="Austin"))
        assert result["status"] == "success" and "note" not in result


class TestPlaceholderVectorsAreNeverStored:
    def test_store_refuses_degraded_embedding(self):
        from backend.services.vector_search_service import VectorSearchService

        job = SimpleNamespace(
            title="Data Engineer", job_overview="Pipelines", required_qualifications="SQL",
            skills="SQL, Python", embedding=None,
        )
        candidate = SimpleNamespace(
            current_position="Data Engineer", current_company="Acme", headline="Pipelines",
            skills=[SimpleNamespace(skill_name="SQL")], embedding=None,
        )
        rows = {"Job": job, "Candidate": candidate}
        committed = []
        db = SimpleNamespace(
            query=lambda model: SimpleNamespace(
                filter=lambda *a: SimpleNamespace(first=lambda: rows[model.__name__])
            ),
            commit=lambda: committed.append(True),
        )
        degraded_model = SimpleNamespace(is_degraded=True, embed_query=lambda text: [0.0] * 768)
        svc = VectorSearchService(embedding_model=degraded_model)
        assert svc.store_job_embedding(db, 1) is False
        assert svc.store_candidate_embedding(db, "abc") is False
        assert job.embedding is None and candidate.embedding is None and committed == []


class TestSuggestionChipsNameRealJobs:
    def test_every_chip_role_exists_in_the_seed(self):
        chat = (REPO / "web/src/components/assistant-chat.tsx").read_text(encoding="utf-8")
        seed = (REPO / "scripts/seed_demo.py").read_text(encoding="utf-8")
        seeded_titles = set(re.findall(r'"title":\s*"([^"]+)"', seed))
        assert seeded_titles, "seed job titles not found"
        chips = re.findall(r'^\s*"([^"]+)",\s*$', chat.split("SUGGESTION_POOL = [")[1].split("];")[0], re.M)
        assert len(chips) >= 4
        named = [m for chip in chips for m in re.findall(r"for the (.+?) role", chip)]
        assert named, "expected at least one chip to name a job"
        for title in named:
            assert title in seeded_titles, f"chip names {title!r}, which the seed does not create"
        # "Why is our top candidate a good fit" sent the model looking for a
        # candidate literally named "top candidate"; a chip that names a
        # person must name one the seed creates.
        people = [m for chip in chips for m in re.findall(r"Why is (.+?) a good fit", chip)]
        for person in people:
            first, last = person.split(" ", 1)
            assert f'("{first}", "{last}"' in seed, f"chip names {person!r}, whom the seed does not create"
