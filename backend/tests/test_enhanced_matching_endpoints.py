"""The /api/enhanced-matching endpoints behind the /matching page.

Pins four defects an ultra review of the matching system found (2026-10-01):
similar-jobs answered every call with a 500, a JSON null min_score slipped
past validation, an agent failure came back as an empty 200 that read as
"nobody matches", and the scoring ran on the event loop.
"""
from __future__ import annotations

import inspect

import pytest

from backend.routers import enhanced_matching, matching


def test_similar_jobs_returns_a_list(admin_client, seed):
    response = admin_client.post(
        "/api/enhanced-matching/similar-jobs",
        json={"job_id": seed["job_id"], "limit": 5},
    )
    assert response.status_code == 200, response.text
    similar = response.json()["similar_jobs"]
    assert isinstance(similar, list)
    assert all(job["id"] != seed["job_id"] for job in similar)


@pytest.mark.parametrize(
    "path, body",
    [
        ("/api/enhanced-matching/match-candidates", {"job_ids": [1], "min_score": None}),
        ("/api/enhanced-matching/match-jobs", {"candidate_id": "x", "min_score": None}),
        ("/api/search/match_jobs", {"candidate_id": "x", "min_score": None}),
    ],
)
def test_null_min_score_is_rejected(admin_client, path, body):
    assert admin_client.post(path, json=body).status_code == 422


def test_agent_error_is_a_500_not_an_empty_list(admin_client, seed, monkeypatch):
    class FailingAgent:
        async def execute(self, task):
            return {"status": "error", "message": "scoring blew up"}

    monkeypatch.setattr(
        enhanced_matching.AgentFactory, "create_agent", staticmethod(lambda *a, **k: FailingAgent())
    )
    response = admin_client.post(
        "/api/enhanced-matching/match-candidates",
        json={"job_ids": [seed["job_id"]], "min_score": 0},
    )
    assert response.status_code == 500
    assert "scoring blew up" in response.json()["detail"]


@pytest.mark.parametrize("router", [enhanced_matching.router, matching.router], ids=["enhanced", "search"])
def test_matching_endpoints_run_off_the_event_loop(router):
    """Scoring is seconds of synchronous ORM and embedding calls. As async def
    it ran on the event loop and stalled every other request on the worker."""
    for route in router.routes:
        assert not inspect.iscoroutinefunction(route.endpoint), route.path
