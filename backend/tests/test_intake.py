"""Getting people into a pipeline (ATS Phase C).

Every way in (apply, manual add, resume save, consider for another role) goes
through `intake_service.add_to_job`, so these tests pin that function and then
each route that calls it.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.models.models import Candidate, Note
from backend.services import intake_service
from backend.utils import parse_quota

from .conftest import SEED_EMAIL_DOMAIN
from .intake_helpers import application_id_for, client_for_role, new_candidate, new_job, unique


@pytest.fixture(scope="module")
def team_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "hiring_team")


@pytest.fixture(scope="module")
def fresh_interviewer_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "interviewer")


def test_add_to_job_starts_the_pipeline_and_is_idempotent(admin_client, db_session):
    job_id = new_job(admin_client)
    cid = new_candidate(admin_client)
    application, created = intake_service.add_to_job(db_session, cid, job_id, source="referral")
    db_session.commit()
    assert created is True
    assert application.status == "active"
    again, created_again = intake_service.add_to_job(db_session, cid, job_id)
    assert created_again is False and again.id == application.id
    detail = admin_client.get(f"/api/applications/{application.id}").json()
    assert detail["current_stage_key"] == "resume_submitted"


def test_add_to_job_sets_position_applied_only_when_blank(admin_client, db_session):
    job_id = new_job(admin_client)
    cid = new_candidate(admin_client, position_applied="Already Chosen")
    intake_service.add_to_job(db_session, cid, job_id)
    db_session.commit()
    assert db_session.get(Candidate, cid).position_applied == "Already Chosen"


@pytest.mark.parametrize("missing", ["job", "candidate"])
def test_add_to_job_names_what_is_missing(admin_client, db_session, missing):
    job_id = new_job(admin_client) if missing == "candidate" else 99999999
    cid = new_candidate(admin_client) if missing == "job" else "00000000-0000-4000-8000-00000000beef"
    with pytest.raises(intake_service.IntakeError) as caught:
        intake_service.add_to_job(db_session, cid, job_id)
    assert caught.value.status_code == 404
    assert missing in caught.value.detail.lower()


def test_apply_still_refuses_a_duplicate(admin_client):
    job_id = new_job(admin_client)
    cid = new_candidate(admin_client)
    assert admin_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid}).status_code == 200
    second = admin_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid})
    assert second.status_code == 400
    assert second.json()["detail"] == "Already applied to this job"


def test_consider_for_another_role_gives_one_person_two_pipelines(admin_client):
    first_job, second_job = new_job(admin_client), new_job(admin_client)
    cid = new_candidate(admin_client, job_id=first_job)
    response = admin_client.post(
        f"/api/jobs/{second_job}/apply", json={"candidate_id": cid, "source": "internal"}
    )
    assert response.status_code == 200, response.text
    rows = admin_client.get(f"/api/jobs/applications/{cid}").json()
    assert sorted(r["job_id"] for r in rows) == sorted([first_job, second_job])
    for row in rows:
        detail = admin_client.get(f"/api/applications/{row['id']}").json()
        assert detail["current_stage_key"] == "resume_submitted"


def test_manual_add_with_a_job_lands_at_stage_one(admin_client, db_session):
    job_id = new_job(admin_client, "Manual Add")
    cid = new_candidate(admin_client, job_id=job_id)
    application_id = application_id_for(admin_client, cid, job_id)
    detail = admin_client.get(f"/api/applications/{application_id}").json()
    assert detail["current_stage_key"] == "resume_submitted"
    assert db_session.get(Candidate, cid).position_applied.startswith("Manual Add")


def test_manual_add_with_an_unknown_job_creates_nothing(admin_client, db_session):
    email = f"{unique('nojob')}@{SEED_EMAIL_DOMAIN}"
    response = admin_client.post(
        "/api/candidates/",
        json={"first_name": "No", "last_name": "Job", "email": email, "job_id": 99999999},
    )
    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.query(Candidate).filter(Candidate.email == email).count() == 0


def test_manual_add_notes_become_the_first_note(admin_client, admin_user, db_session):
    cid = new_candidate(admin_client, notes="  Met at the meetup.  ")
    db_session.expire_all()
    assert db_session.get(Candidate, cid).notes is None
    notes = db_session.query(Note).filter(Note.candidate_id == cid).all()
    assert [n.body for n in notes] == ["Met at the meetup."]
    assert notes[0].author_id == admin_user.id


def test_update_no_longer_writes_the_old_notes_column(admin_client, db_session):
    cid = new_candidate(admin_client)
    response = admin_client.put(f"/api/candidates/{cid}", json={"notes": "ignored", "headline": "Kept"})
    assert response.status_code == 200, response.text
    db_session.expire_all()
    candidate = db_session.get(Candidate, cid)
    assert candidate.notes is None and candidate.headline == "Kept"


def test_intake_follows_the_permission_matrix(team_client, fresh_interviewer_client, demo_client, admin_client):
    job_id = new_job(admin_client)

    def payload():
        return {"first_name": "Perm", "last_name": "Check", "email": f"{unique('perm')}@{SEED_EMAIL_DOMAIN}"}

    assert demo_client.post("/api/candidates/", json=payload()).status_code == 403
    assert fresh_interviewer_client.post("/api/candidates/", json=payload()).status_code == 403
    created = team_client.post("/api/candidates/", json={**payload(), "job_id": job_id})
    assert created.status_code == 200, created.text

    cid = new_candidate(admin_client)
    assert fresh_interviewer_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid}).status_code == 403
    assert team_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid}).status_code == 200


SAVE_PATH = "/api/resume/save-candidate"


def _save_form(email: str, job_id=None):
    data = {
        "parsed_data": json.dumps(
            {
                "personal_info": {"name": "Upload Intake", "email": email},
                "skills": ["Python"],
                "experience": [{"company": "Analytical Engines", "title": "Engineer"}],
            }
        )
    }
    if job_id is not None:
        data["job_id"] = str(job_id)
    return {"files": {"file": ("resume.txt", b"Upload Intake. Engineer.", "text/plain")}, "data": data}


def test_save_with_a_job_lands_at_stage_one(admin_client):
    job_id = new_job(admin_client, "Upload Target")
    form = _save_form(f"{unique('upload')}@{SEED_EMAIL_DOMAIN}", job_id)
    response = admin_client.post(SAVE_PATH, **form)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["application_id"] and body["already_in_pipeline"] is False
    detail = admin_client.get(f"/api/applications/{body['application_id']}").json()
    assert detail["job_id"] == job_id
    assert detail["current_stage_key"] == "resume_submitted"

    # Saving the same person again to the same job is not an error.
    again = admin_client.post(SAVE_PATH, **form).json()
    assert again["application_id"] == body["application_id"]
    assert again["already_in_pipeline"] is True


def test_save_without_a_job_is_unchanged(admin_client):
    response = admin_client.post(SAVE_PATH, **_save_form(f"{unique('nojob')}@{SEED_EMAIL_DOMAIN}"))
    assert response.status_code == 200, response.text
    assert response.json()["application_id"] is None


def test_save_with_an_unknown_job_stores_nothing(admin_client, db_session):
    email = f"{unique('badjob')}@{SEED_EMAIL_DOMAIN}"
    response = admin_client.post(SAVE_PATH, **_save_form(email, 99999999))
    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.query(Candidate).filter(Candidate.email == email).count() == 0


def test_hiring_team_can_save_and_interviewers_cannot(team_client, fresh_interviewer_client):
    ok = team_client.post(SAVE_PATH, **_save_form(f"{unique('team')}@{SEED_EMAIL_DOMAIN}"))
    assert ok.status_code == 200, ok.text
    refused = fresh_interviewer_client.post(SAVE_PATH, **_save_form(f"{unique('int')}@{SEED_EMAIL_DOMAIN}"))
    assert refused.status_code == 403


def test_roles_that_add_candidates_skip_the_parse_quota(monkeypatch):
    calls = []

    async def fake_redis():
        calls.append(1)
        raise RuntimeError("the quota should not have been checked")

    monkeypatch.setattr("backend.utils.redis_client.get_redis_client", fake_redis)
    monkeypatch.setattr(parse_quota, "get_settings", lambda: SimpleNamespace(parse_daily_limit=20))
    request = SimpleNamespace(headers={}, client=None)

    for role in ("admin", "hiring_manager", "hiring_team"):
        asyncio.run(parse_quota.enforce_parse_quota(request, current_user=SimpleNamespace(role=role)))
    assert calls == []

    asyncio.run(parse_quota.enforce_parse_quota(request, current_user=SimpleNamespace(role="interviewer")))
    assert calls == [1]  # interviewers are counted like anyone else


def test_jobs_report_active_applications_from_the_pipeline(admin_client):
    job_id = new_job(admin_client, "Count Check")
    first = new_candidate(admin_client, job_id=job_id)
    new_candidate(admin_client, job_id=job_id)
    admin_client.post(f"/api/applications/{application_id_for(admin_client, first, job_id)}/reject", json={})

    detail = admin_client.get(f"/api/jobs/{job_id}").json()
    assert detail["active_applications"] == 1
    assert detail["applications"] == 2  # the stored all-time counter is unchanged
    listed = admin_client.get("/api/jobs/?page_size=100&keyword=Count Check").json()["results"]
    assert next(j for j in listed if j["id"] == job_id)["active_applications"] == 1
