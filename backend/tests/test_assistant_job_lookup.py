"""Job lookups the assistant does against the real schema.

From the 2026-09-30 review of PR #25: a title inside several job titles
resolved to whichever row Postgres returned first, the "open" job list fell
back to closed jobs, and a candidate's applied job was labelled with their
free-text position instead of the job's real title. Every test runs inside a
savepoint on the contract seed, so the extra jobs and status changes vanish.
"""
from __future__ import annotations

import asyncio
import re

import pytest

from backend.models.models import Candidate, Job
from backend.services.assistant_tools import build_assistant_tools


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def scratch(db_session, seed):
    """The seeded session inside a savepoint that is rolled back afterwards."""
    savepoint = db_session.begin_nested()
    try:
        yield db_session
    finally:
        savepoint.rollback()
        db_session.expire_all()


def _tools(db):
    return {t.name: t for t in build_assistant_tools(db)}


def _add_jobs(db, *titles, status="open"):
    jobs = [Job(title=t, department="Test", status=status, skills="Python") for t in titles]
    db.add_all(jobs)
    db.flush()
    return jobs


class TestTitleLookup:
    # A made-up word, so a loaded dev database has no other job containing it.
    def test_title_inside_several_jobs_asks_which_one(self, scratch):
        _add_jobs(scratch, "Senior Zyxquor Analyst", "Junior Zyxquor Analyst")
        result = run(_tools(scratch)["get_job"].run(job="Zyxquor Analyst"))
        assert "error" in result and "id" not in result, result
        assert {j["title"] for j in result["matching_jobs"]} == {"Senior Zyxquor Analyst", "Junior Zyxquor Analyst"}
        assert not re.search(r"\b(tell the user|do not|never|you must)\b", result["note"], re.I)

    def test_match_to_job_does_not_rank_an_ambiguous_title(self, scratch):
        _add_jobs(scratch, "Senior Zyxquor Analyst", "Junior Zyxquor Analyst")
        result = run(_tools(scratch)["match_to_job"].run(job="Zyxquor Analyst"))
        assert "matches" not in result and result["matching_jobs"]

    def test_exact_title_wins_over_longer_ones(self, scratch):
        _add_jobs(scratch, "Senior Zyxquor Analyst", "Zyxquor Analyst", "Junior Zyxquor Analyst")
        result = run(_tools(scratch)["get_job"].run(job="zyxquor analyst"))
        assert result.get("title") == "Zyxquor Analyst", result

    def test_open_job_wins_an_exact_tie(self, scratch):
        _add_jobs(scratch, "Zyxquor Analyst", status="closed")
        (open_job,) = _add_jobs(scratch, "Zyxquor Analyst")
        result = run(_tools(scratch)["get_job"].run(job="Zyxquor Analyst"))
        assert result.get("id") == open_job.id, result

    def test_single_partial_hit_is_that_job(self, scratch):
        _add_jobs(scratch, "Senior Zyxquor Analyst", "Junior Zyxquor Analyst")
        result = run(_tools(scratch)["get_job"].run(job="Senior Zyxquor"))
        assert result.get("title") == "Senior Zyxquor Analyst", result


class TestOpenJobList:
    def test_pipeline_never_lists_closed_jobs_as_open(self, scratch):
        scratch.query(Job).update({Job.status: "closed"})
        scratch.flush()
        result = run(_tools(scratch)["list_pipeline"].run())
        assert result["open_jobs"] == 0
        assert result["open_job_list"] == []


class TestAppliedJob:
    def test_applied_job_carries_the_jobs_own_title_and_status(self, scratch, seed):
        ada = scratch.query(Candidate).filter(Candidate.id == seed["candidate_id"]).one()
        ada.position_applied = "Sr. Data Eng"
        scratch.query(Job).filter(Job.id == ada.job_id).update({Job.status: "closed"})
        scratch.flush()
        result = run(_tools(scratch)["get_candidate"].run(candidate=seed["candidate_id"]))
        assert result["applied_job"] == {"id": ada.job_id, "title": "Senior Data Engineer", "status": "closed"}
