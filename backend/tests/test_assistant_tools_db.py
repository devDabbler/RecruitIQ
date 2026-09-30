"""DB-integration tests for the assistant tools (skipped without Postgres)."""
import asyncio
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

POSTGRES_CONN = os.getenv("POSTGRES_CONN", "").strip('"')


def _db_available():
    if not POSTGRES_CONN:
        return False
    try:
        engine = create_engine(POSTGRES_CONN)
        with engine.connect() as conn:
            return conn.execute(text("SELECT count(*) FROM candidates")).scalar() is not None
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="needs Postgres with app schema")


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def db():
    engine = create_engine(POSTGRES_CONN)
    session = sessionmaker(bind=engine)()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def tools(db):
    from backend.services.assistant_tools import build_assistant_tools

    return {t.name: t for t in build_assistant_tools(db)}


class TestPipelineTool:
    def test_counts_are_consistent(self, db, tools):
        result = run(tools["list_pipeline"].run())
        assert result["total_candidates"] >= 0
        assert sum(result["candidates_by_status"].values()) == result["total_candidates"]
        assert result["open_jobs"] <= result["total_jobs"]


class TestLookupTools:
    def test_get_job_by_title(self, db, tools):
        from backend.models.models import Job

        any_job = db.query(Job).first()
        if any_job is None:
            pytest.skip("no jobs seeded")
        result = run(tools["get_job"].run(job=any_job.title))
        assert result.get("id") is not None
        assert "error" not in result

    def test_get_job_not_found(self, db, tools):
        result = run(tools["get_job"].run(job="zzz-not-a-job-zzz"))
        # Below the semantic floor (or with embeddings degraded) the tool must
        # say so and list the real titles, never substitute the nearest job.
        assert "error" in result and "id" not in result
        assert isinstance(result["open_jobs"], list)

    def test_get_job_nonsense_title_is_refused(self, db, tools):
        from backend.models.models import Job

        if db.query(Job).filter(Job.embedding.isnot(None)).count() == 0:
            pytest.skip("needs jobs with embeddings")
        result = run(tools["get_job"].run(job="Chief Happiness Officer"))
        assert "error" in result, result
        assert "Chief Happiness Officer" in result["note"]

    def test_get_candidate_by_name(self, db, tools):
        from backend.models.models import Candidate

        any_candidate = db.query(Candidate).first()
        if any_candidate is None:
            pytest.skip("no candidates seeded")
        result = run(tools["get_candidate"].run(candidate=any_candidate.first_name or any_candidate.id))
        assert "error" not in result
        assert result["id"]
        assert isinstance(result["skills"], list)

    def test_get_candidate_not_found(self, db, tools):
        result = run(tools["get_candidate"].run(candidate="zzz-nobody-zzz"))
        assert "error" in result

    @pytest.mark.parametrize("lookup", ["%", "_", "%%", "", "  ", "\\"])
    def test_wildcards_are_not_a_candidate_lookup(self, db, tools, lookup):
        # get_candidate("%") used to return the first row in the table: the
        # name goes into an ILIKE pattern, and % and _ are its wildcards.
        result = run(tools["get_candidate"].run(candidate=lookup))
        assert "error" in result and "id" not in result, result

    @pytest.mark.parametrize("lookup", ["%", "_", "%%", "", "  "])
    def test_wildcards_are_not_a_job_lookup(self, db, tools, lookup):
        result = run(tools["get_job"].run(job=lookup))
        # Either no job at all, or the semantic fallback's honest form; never
        # a direct hit that ILIKE handed over because the pattern was "%%%".
        assert "error" in result or result.get("matched_by") == "semantic", result

    def test_resume_tool_frames_the_document(self, db, tools):
        from backend.models.models import Resume
        from backend.services.assistant_tools import RESUME_FRAMING_NOTE

        resume = db.query(Resume).filter(Resume.parsed_content.isnot(None)).first()
        if resume is None:
            pytest.skip("no parsed resumes")
        result = run(tools["get_candidate_resume"].run(candidate=resume.candidate_id))
        assert "error" not in result, result
        assert result["note"] == RESUME_FRAMING_NOTE
        assert result["candidate_id"] == resume.candidate_id
        assert result["parsed_content"]


class TestSearchCandidatesLocationFallback:
    def test_unmatched_location_returns_candidates_elsewhere(self, db, tools):
        """When the place filter matches nobody, the tool itself re-runs the
        search unfiltered so the model never has to make a second call."""
        from sqlalchemy import text as sql_text

        has_embeddings = db.execute(
            sql_text("SELECT count(*) FROM candidates WHERE embedding IS NOT NULL")
        ).scalar()
        if not has_embeddings:
            pytest.skip("needs candidates with embeddings")

        result = run(
            tools["search_candidates"].run(
                query="software engineer", location="zzz-nowhere-land"
            )
        )
        if result.get("search_degraded"):
            pytest.skip("embedding service unreachable; the tool now reports that instead of guessing")
        assert result["count"] == 0 and result["candidates"] == []
        assert result["location_filter"] == "zzz-nowhere-land"
        assert len(result["candidates_elsewhere"]) > 0
        assert "note" in result and "zzz-nowhere-land" in result["note"]

    def test_anywhere_is_dropped_not_filtered(self, db, tools):
        """"Anywhere" from the model must not become a location filter: the
        result carries plain matches, with no location_filter to apologize
        for and no candidates_elsewhere detour."""
        from sqlalchemy import text as sql_text

        has_embeddings = db.execute(
            sql_text("SELECT count(*) FROM candidates WHERE embedding IS NOT NULL")
        ).scalar()
        if not has_embeddings:
            pytest.skip("needs candidates with embeddings")

        result = run(
            tools["search_candidates"].run(query="software engineer", location="Anywhere")
        )
        if result.get("search_degraded"):
            pytest.skip("embedding service unreachable; the tool now reports that instead of guessing")
        assert result["count"] > 0
        assert "location_filter" not in result
        assert "candidates_elsewhere" not in result
