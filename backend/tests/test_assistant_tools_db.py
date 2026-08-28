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
        # Semantic fallback may still return the closest job; accept either an
        # error or a well-formed job dict, never an exception.
        assert "error" in result or "id" in result

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
