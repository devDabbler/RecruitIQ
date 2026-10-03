"""Interviewer scoping and score hiding (ATS Phase B, spec section 8).

The route walk mirrors test_auth: instead of listing read routes by hand it
walks the application's own route table, so a read endpoint added later is
closed to interviewers the moment it exists unless someone adds it to
INTERVIEWER_PATHS on purpose.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from backend.main import app
from backend.models.models import JobApplication
from backend.services import feedback_service as fs
from backend.services import pipeline_service as ps
from backend.services.access_service import INTERVIEWER_PATHS, SCORE_HIDDEN_DETAIL
from backend.tests.test_auth import _concrete
from backend.utils.auth import READ_ONLY_POST_PATHS


@pytest.fixture(scope="module")
def assigned(db_session, scoped_application, staff_users):
    application = db_session.get(JobApplication, scoped_application["application_id"])
    interview = fs.assign(db_session, ps.current_stage(application), staff_users["interviewer"])
    db_session.commit()
    return {**scoped_application, "interview_id": interview.id}


def _reads():
    out = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue  # /docs and /openapi.json are not behind the app dependencies
        normalized = route.path.rstrip("/") or "/"
        if "GET" in route.methods:
            out.append(("GET", route.path))
        if "POST" in route.methods and normalized in READ_ONLY_POST_PATHS:
            out.append(("POST", route.path))
    return out


def _allowlisted(path: str) -> bool:
    concrete = _concrete(path).rstrip("/") or "/"
    return any(pattern.fullmatch(concrete) for pattern, _ in INTERVIEWER_PATHS)


CLOSED = [(method, path) for method, path in _reads() if not _allowlisted(path)]


def test_the_closed_list_covers_the_legacy_surface():
    paths = {path for _, path in CLOSED}
    assert len(CLOSED) > 20
    assert "/api/assistant/chat" in paths
    assert "/api/transparency/match-trace" in paths


@pytest.mark.parametrize(("method", "path"), CLOSED, ids=[f"{m} {p}" for m, p in CLOSED])
def test_interviewers_are_refused_everything_off_the_allowlist(interviewer_client, method, path):
    kwargs = {"json": {}} if method == "POST" else {}
    response = interviewer_client.request(method, _concrete(path), **kwargs)
    assert response.status_code == 403, f"{method} {path} answered {response.status_code}"


def test_skills_breakdown_is_closed_to_interviewers(interviewer_client):
    # Matches the candidate-id pattern, and "skills_breakdown" is nobody's id.
    assert interviewer_client.get("/api/candidates/skills_breakdown").status_code == 404


def test_candidate_list_shows_only_assigned(interviewer_client, assigned):
    body = interviewer_client.get("/api/candidates/", params={"page_size": 100}).json()
    assert [c["id"] for c in body["results"]] == [assigned["candidate_id"]]
    assert body["total"] == 1


def test_other_candidates_are_not_found(interviewer_client, assigned, seed):
    other = seed["candidate_ids"][0]
    assert interviewer_client.get(f"/api/candidates/{other}").status_code == 404
    assert interviewer_client.get(f"/api/candidates/{other}/resumes").status_code == 404
    assert interviewer_client.get(f"/api/jobs/applications/{other}").status_code == 404
    assert interviewer_client.get(f"/api/applications/{seed['application_id']}").status_code == 404
    assert interviewer_client.get(f"/api/resume/{seed['resume_id']}").status_code == 404
    assert interviewer_client.get(f"/api/candidates/{assigned['candidate_id']}").status_code == 200
    assert interviewer_client.get(f"/api/applications/{assigned['application_id']}").status_code == 200


def test_board_shows_only_assigned(interviewer_client, assigned, seed):
    def candidates_on(job_id):
        body = interviewer_client.get(f"/api/jobs/{job_id}/pipeline").json()
        return {card["candidate_id"] for col in body["columns"] for card in col["applications"]}

    assert candidates_on(seed["job_id"]) <= {assigned["candidate_id"]}
    assert candidates_on(assigned["job_id"]) == {assigned["candidate_id"]}


def test_other_roles_still_see_everyone(hiring_team_client, demo_client, seed, assigned):
    for client in (hiring_team_client, demo_client):
        body = client.get("/api/candidates/", params={"page_size": 100}).json()
        assert set(seed["candidate_ids"]) <= {c["id"] for c in body["results"]}


def test_score_is_hidden_until_feedback(interviewer_client, hiring_team_client, assigned):
    body = {"candidate_id": assigned["candidate_id"], "min_score": 0}
    before = interviewer_client.post("/api/enhanced-matching/match-jobs", json=body)
    assert before.status_code == 403
    assert before.json()["detail"] == SCORE_HIDDEN_DETAIL
    assert hiring_team_client.post("/api/enhanced-matching/match-jobs", json=body).status_code != 403

    given = interviewer_client.post(
        f"/api/interviews/{assigned['interview_id']}/feedback",
        json={"rating": 4, "recommendation": "hire", "notes": "Clear thinker."},
    )
    assert given.status_code == 200, given.text
    # Matching itself may still fail without embeddings in CI; the point is
    # that the score gate no longer refuses.
    after = interviewer_client.post("/api/enhanced-matching/match-jobs", json=body)
    assert after.status_code != 403


def test_interviewers_can_reach_their_own_screens(interviewer_client, assigned):
    for path in ("/auth/me", "/api/interviews", "/api/jobs/", "/api/transparency/policy"):
        assert interviewer_client.get(path).status_code == 200, path
