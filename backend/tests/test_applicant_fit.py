"""Track 2 Phase 2: a job's applicants ranked by fit.

What is pinned here:

* board cards and the job-filtered candidate list carry the same number
  `score_pair` gives, caps included;
* `sort_by=fit` ranks the job's applicants (best first by default) and pages
  the ranked list;
* an interviewer sees no score, and no cap detail, for a candidate until they
  have submitted feedback on them, and their list order does not leak it;
* the resume save path returns the new applicant's fit for the bulk uploader;
* a cold title cache costs one batched embedding call, and an outage one
  failed call, not one per title.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.models import Candidate, CandidateSkill, Job, JobApplication, User
from backend.services import feedback_service as fs
from backend.services import pipeline_service as ps
from backend.services.matching_enhancer import MatchingEnhancer, _request_placeholders
from backend.services.service_registry import get_registry
from backend.utils.auth import create_access_token

from .conftest import SEED_EMAIL_DOMAIN, SEED_EPOCH
from .intake_helpers import application_id_for, unique

REQUIREMENTS = {"must_have_skills": ["Python", "Rust"]}

# (current position, skills): a full match, one missing must-have, a stranger.
APPLICANTS = [
    ("Backend Engineer", ("Python", "Rust", "SQL", "Kubernetes")),
    ("Backend Engineer", ("Python", "SQL")),
    ("Pastry Chef", ("Baking",)),
]


def _staff(db_session, role: str) -> tuple[TestClient, User]:
    user = User(
        email=f"{unique(role)}@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role=role,
        name=f"Fit {role}",
        created_at=SEED_EPOCH,
    )
    db_session.add(user)
    db_session.commit()
    client = TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Authorization": f"Bearer {create_access_token(user)}"},
    )
    return client, user


@pytest.fixture(scope="module")
def ranked_job(admin_client, db_session):
    created = admin_client.post(
        "/api/jobs/",
        json={
            "title": f"Backend Engineer {unique('fit')}",
            "department": "Engineering",
            "job_overview": "Build services.",
            "required_qualifications": "Python",
            "skills": ["Python", "SQL"],
            "requirements": REQUIREMENTS,
            "status": "open",
        },
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]

    ids = []
    for position, skills in APPLICANTS:
        cid = str(uuid.uuid4())
        db_session.add(
            Candidate(
                id=cid,
                first_name="Fit",
                last_name=position.split()[0],
                email=f"{unique('fit')}@{SEED_EMAIL_DOMAIN}",
                current_position=position,
                created_at=datetime(2026, 1, 1),
            )
        )
        db_session.flush()
        for skill in skills:
            db_session.add(CandidateSkill(candidate_id=cid, skill_name=skill))
        db_session.commit()
        applied = admin_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid})
        assert applied.status_code == 200, applied.text
        ids.append(cid)
    return {"job_id": job_id, "candidate_ids": ids}


def _expected(db_session, job_id: int, candidate_id: str) -> dict:
    db_session.expire_all()
    trace = get_registry().matching_integrator.score_pair(
        db_session.get(Job, job_id), db_session.get(Candidate, candidate_id)
    )
    return trace


def _cards(client, job_id) -> dict:
    body = client.get(f"/api/jobs/{job_id}/pipeline").json()
    return {card["candidate_id"]: card for col in body["columns"] for card in col["applications"]}


def _listed(client, job_id, **params) -> list:
    response = client.get(
        "/api/candidates/", params={"job_id": job_id, "page_size": 100, **params}
    )
    assert response.status_code == 200, response.text
    return response.json()["results"]


def test_board_cards_carry_the_score_pair_number(admin_client, db_session, ranked_job):
    cards = _cards(admin_client, ranked_job["job_id"])
    assert set(cards) == set(ranked_job["candidate_ids"])
    for cid in ranked_job["candidate_ids"]:
        trace = _expected(db_session, ranked_job["job_id"], cid)
        fit = cards[cid]["fit"]
        assert fit["hidden"] is False
        assert fit["score"] == pytest.approx(trace["match_score"], abs=0.05)
        assert fit["capped"] is trace["requirement_cap"]["applied"]
        assert fit["missing"] == trace["requirement_cap"]["missing"]

    full, partial, _ = ranked_job["candidate_ids"]
    assert cards[full]["fit"]["missing"] == []
    assert cards[partial]["fit"]["missing"] == ["must-have skill Rust"]


def test_list_sorted_by_fit_is_best_first_and_pages(admin_client, ranked_job):
    job_id = ranked_job["job_id"]
    best_first = _listed(admin_client, job_id, sort_by="fit")
    scores = [row["fit"]["score"] for row in best_first]
    assert len(scores) == 3 and scores == sorted(scores, reverse=True)
    assert best_first[0]["id"] == ranked_job["candidate_ids"][0]

    worst_first = _listed(admin_client, job_id, sort_by="fit", sort_order="asc")
    assert [r["id"] for r in worst_first] == [r["id"] for r in reversed(best_first)]

    second = admin_client.get(
        "/api/candidates/", params={"job_id": job_id, "sort_by": "fit", "page": 2, "page_size": 1}
    ).json()
    assert second["total"] == 3
    assert [r["id"] for r in second["results"]] == [best_first[1]["id"]]


def test_list_carries_fit_only_with_a_job(admin_client, ranked_job):
    rows = _listed(admin_client, ranked_job["job_id"])
    assert all(row["fit"] and row["fit"]["score"] is not None for row in rows)
    unfiltered = admin_client.get("/api/candidates/", params={"page_size": 5}).json()["results"]
    assert all(row["fit"] is None for row in unfiltered)


def test_sorting_by_fit_needs_a_job(admin_client):
    response = admin_client.get("/api/candidates/", params={"sort_by": "fit"})
    assert response.status_code == 400
    assert "job_id" in response.json()["detail"]


def test_interviewer_sees_no_score_until_feedback(db_session, ranked_job):
    client, user = _staff(db_session, "interviewer")
    job_id = ranked_job["job_id"]
    partial = ranked_job["candidate_ids"][1]  # the capped one: cap detail must hide too
    application = db_session.get(JobApplication, application_id_for_db(db_session, partial, job_id))
    interview = fs.assign(db_session, ps.current_stage(application), user)
    db_session.commit()

    cards = _cards(client, job_id)
    assert set(cards) == {partial}
    assert cards[partial]["fit"] == {"score": None, "hidden": True, "capped": False, "missing": []}
    rows = _listed(client, job_id, sort_by="fit")
    assert [r["id"] for r in rows] == [partial]
    assert rows[0]["fit"]["hidden"] is True and rows[0]["fit"]["score"] is None

    given = client.post(
        f"/api/interviews/{interview.id}/feedback",
        json={"rating": 3, "recommendation": "hire", "notes": "Solid."},
    )
    assert given.status_code == 200, given.text

    fit = _cards(client, job_id)[partial]["fit"]
    assert fit["hidden"] is False and fit["score"] is not None
    assert fit["missing"] == ["must-have skill Rust"]


def application_id_for_db(db_session, candidate_id: str, job_id: int) -> int:
    db_session.expire_all()
    return (
        db_session.query(JobApplication.id)
        .filter(JobApplication.candidate_id == candidate_id, JobApplication.job_id == job_id)
        .scalar()
    )


def test_resume_save_returns_the_new_applicants_fit(admin_client, ranked_job):
    form = {
        "parsed_data": json.dumps(
            {
                "personal_info": {"name": "Bulk Fit", "email": f"{unique('bulkfit')}@{SEED_EMAIL_DOMAIN}"},
                "skills": ["Python", "Rust"],
                "experience": [{"company": "Analytical Engines", "title": "Backend Engineer"}],
            }
        ),
        "job_id": str(ranked_job["job_id"]),
    }
    response = admin_client.post(
        "/api/resume/save-candidate",
        files={"file": ("resume.txt", b"Bulk Fit. Backend Engineer.", "text/plain")},
        data=form,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fit"]["hidden"] is False
    assert isinstance(body["fit"]["score"], float)
    # The same number the board shows for them.
    card = _cards(admin_client, ranked_job["job_id"])[body["candidate_id"]]
    assert card["fit"]["score"] == body["fit"]["score"]
    assert application_id_for(admin_client, body["candidate_id"], ranked_job["job_id"]) == body["application_id"]


def test_resume_save_without_a_job_has_no_fit(admin_client):
    form = {
        "parsed_data": json.dumps(
            {"personal_info": {"name": "No Job", "email": f"{unique('nojobfit')}@{SEED_EMAIL_DOMAIN}"}}
        )
    }
    response = admin_client.post(
        "/api/resume/save-candidate",
        files={"file": ("resume.txt", b"No Job.", "text/plain")},
        data=form,
    )
    assert response.status_code == 200, response.text
    assert response.json()["fit"] is None


class CountingModel:
    def __init__(self, degraded: bool = False):
        self.is_degraded = degraded
        self.batches: list[list[str]] = []
        self.singles: list[str] = []

    def embed_documents(self, texts):
        self.batches.append(list(texts))
        return [[float(len(t)), 1.0, 0.0] for t in texts]

    def embed_query(self, text):
        self.singles.append(text)
        return [float(len(text)), 1.0, 0.0]


def test_priming_embeds_every_title_in_one_call():
    model = CountingModel()
    enhancer = MatchingEnhancer(embedding_model=model)
    enhancer.prime_titles(["Data Engineer", "data engineer", "Chef", "", None, "  "])
    assert model.batches == [["data engineer", "chef"]]

    enhancer.role_match_details("Data Engineer", "", "Chef")
    assert model.singles == []  # both titles came from the primed cache
    enhancer.prime_titles(["Chef"])
    assert len(model.batches) == 1  # nothing left to embed


def test_an_outage_costs_one_call_per_ranking_and_is_not_cached():
    model = CountingModel(degraded=True)
    enhancer = MatchingEnhancer(embedding_model=model)
    token = _request_placeholders.set(None)
    try:
        enhancer.prime_titles(["Data Engineer", "Chef"])
        enhancer.role_match_details("Data Engineer", "", "Chef")
        assert model.singles == []
        assert enhancer._embedding_cache == {}
    finally:
        _request_placeholders.reset(token)
