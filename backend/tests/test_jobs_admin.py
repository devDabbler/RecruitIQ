"""Admin job management, and the matching behaviour it exposes.

Authorisation is deliberately *not* re-tested here: `test_auth.py` walks the
application's route table and asserts every mutating route refuses both the demo
role and anonymous callers, so create/update/delete are already covered the
moment they exist. What is covered here is the behaviour those routes have once
you are allowed through them.
"""
from __future__ import annotations

import pytest

from backend.models.models import Candidate, Job, JobApplication, SavedJob
from backend.tests.conftest import SEED_EPOCH


def _job_payload(**overrides):
    payload = {
        "title": "Staff Platform Engineer",
        "department": "Infrastructure",
        "job_overview": "Own the deployment platform.",
        "required_qualifications": "Kubernetes, Terraform, 7+ years",
        "location": "Remote",
        "location_type": "remote",
        "job_type": "full_time",
        "experience_level": "lead",
        "min_salary": 180000,
        "max_salary": 230000,
        "status": "draft",
        "skills": ["Kubernetes", "Terraform", "Go"],
    }
    payload.update(overrides)
    return payload


# --- create -----------------------------------------------------------------


def test_admin_can_create_a_job(admin_client):
    response = admin_client.post("/api/jobs/", json=_job_payload())
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["title"] == "Staff Platform Engineer"
    assert body["status"] == "draft"
    # The column stores a comma-separated string; the API contract is a list.
    assert body["skills"] == ["Kubernetes", "Terraform", "Go"]


def test_creating_a_job_without_required_fields_is_rejected(admin_client):
    payload = _job_payload()
    del payload["title"]
    assert admin_client.post("/api/jobs/", json=payload).status_code == 422


def test_a_created_job_is_readable_back(admin_client):
    created = admin_client.post(
        "/api/jobs/", json=_job_payload(title="Readback Engineer")
    ).json()
    fetched = admin_client.get(f"/api/jobs/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Readback Engineer"


# --- update -----------------------------------------------------------------


def test_admin_can_edit_a_job(admin_client):
    created = admin_client.post("/api/jobs/", json=_job_payload()).json()

    response = admin_client.put(
        f"/api/jobs/{created['id']}",
        json=_job_payload(title="Principal Platform Engineer", status="open"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Principal Platform Engineer"
    assert response.json()["status"] == "open"


def test_editing_an_unknown_job_is_404(admin_client):
    assert admin_client.put("/api/jobs/99999999", json=_job_payload()).status_code == 404


# --- delete -----------------------------------------------------------------


def test_deleting_a_job_detaches_candidates_and_removes_its_records(
    admin_client, db_session
):
    """The case that used to 500.

    `candidates.job_id` is a foreign key with no relationship declared on `Job`,
    so the ORM never nulled it and Postgres refused the delete. Any job a
    candidate had ever been attached to was undeletable, which is every job in a
    realistic database.
    """
    job = Job(
        title="Doomed Requisition",
        department="Engineering",
        job_overview="Slated for deletion.",
        required_qualifications="None",
        location_type="remote",
        job_type="full_time",
        experience_level="mid",
        status="open",
        skills="Python",
        job_metadata={},
        views=0,
        applications=0,
        created_at=SEED_EPOCH,
        updated_at=SEED_EPOCH,
    )
    db_session.add(job)
    db_session.flush()

    candidate_id = "00000000-0000-4000-8000-0000000009e1"
    db_session.add(
        Candidate(
            id=candidate_id,
            first_name="Detach",
            last_name="Me",
            email="detach-me@recruitiq-seed.example.com",
            status="active",
            job_id=job.id,
            current_position="Engineer",
            created_at=SEED_EPOCH,
            updated_at=SEED_EPOCH,
        )
    )
    db_session.flush()
    db_session.add_all(
        [
            JobApplication(
                job_id=job.id,
                candidate_id=candidate_id,
                status="reviewing",
                applied_at=SEED_EPOCH,
                updated_at=SEED_EPOCH,
                source="direct",
            ),
            SavedJob(job_id=job.id, candidate_id=candidate_id, saved_at=SEED_EPOCH),
        ]
    )
    db_session.flush()
    job_id = job.id

    response = admin_client.delete(f"/api/jobs/{job_id}")
    assert response.status_code == 200, response.text

    db_session.expire_all()
    assert db_session.query(Job).filter(Job.id == job_id).first() is None
    assert db_session.query(JobApplication).filter(JobApplication.job_id == job_id).count() == 0
    assert db_session.query(SavedJob).filter(SavedJob.job_id == job_id).count() == 0

    # The person outlives the requisition, merely detached from it.
    survivor = db_session.query(Candidate).filter(Candidate.id == candidate_id).first()
    assert survivor is not None
    assert survivor.job_id is None


def test_deleting_an_unknown_job_is_404_not_500(admin_client):
    """The handler used to catch its own 404 and re-raise it as a 500."""
    response = admin_client.delete("/api/jobs/99999999")
    assert response.status_code == 404


# --- matching only considers open roles -------------------------------------


@pytest.mark.asyncio
async def test_only_open_jobs_are_matched_to_a_candidate(db_session, seed):
    """A draft is not a role anyone can be put forward for.

    Without the status filter, saving a draft in the jobs UI immediately
    surfaced it in every candidate's matches.
    """
    from backend.services.matching_integrator import MatchingIntegrator

    common = dict(
        department="Engineering",
        job_overview="Identical apart from status.",
        required_qualifications="Python, SQL",
        location_type="remote",
        job_type="full_time",
        experience_level="senior",
        skills="Python,SQL",
        job_metadata={},
        views=0,
        applications=0,
        created_at=SEED_EPOCH,
        updated_at=SEED_EPOCH,
    )
    open_job = Job(title="Visible Open Role", status="open", **common)
    draft_job = Job(title="Hidden Draft Role", status="draft", **common)
    closed_job = Job(title="Hidden Closed Role", status="closed", **common)
    db_session.add_all([open_job, draft_job, closed_job])
    db_session.flush()

    # No embedding model: role similarity falls back to a constant, which keeps
    # this test off the network. It is asserting which rows are considered, not
    # how they score.
    integrator = MatchingIntegrator(embedding_model=None)
    matches = await integrator.enhanced_job_candidate_matching(
        seed["candidate_id"], db_session, min_score=0, limit=100
    )
    matched_ids = {match["id"] for match in matches}

    assert open_job.id in matched_ids
    assert draft_job.id not in matched_ids
    assert closed_job.id not in matched_ids
