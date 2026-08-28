"""POST /api/resume/save-candidate: the write path behind the upload screen.

The endpoint is deliberately absent from READ_ONLY_POST_PATHS, so the app-wide
gate must refuse anonymous callers and the demo role before the handler runs.
These tests pin that refusal, the payload validation, and the one thing the
feature exists for: a reviewed parse becoming a candidate row with a resume
attached, without re-running the model.
"""
from __future__ import annotations

import json

from .conftest import SEED_EMAIL_DOMAIN

SAVE_PATH = "/api/resume/save-candidate"


def _form(parsed_data: str):
    return {
        "files": {"file": ("resume.txt", b"April Drake. Engineer.", "text/plain")},
        "data": {"parsed_data": parsed_data},
    }


def _valid_parse() -> str:
    return json.dumps(
        {
            "personal_info": {
                "name": "Saved Fromparse",
                "email": f"saved.fromparse@{SEED_EMAIL_DOMAIN}",
                "phone": "555-0100",
            },
            "skills": ["Python", {"name": "SQL"}],
            "experience": [{"company": "Analytical Engines", "title": "Engineer"}],
        }
    )


def test_anonymous_save_is_refused(client):
    kwargs = _form(_valid_parse())
    response = client.post(SAVE_PATH, files=kwargs["files"], data=kwargs["data"])
    assert response.status_code == 401


def test_demo_role_save_is_refused(demo_client):
    kwargs = _form(_valid_parse())
    response = demo_client.post(SAVE_PATH, files=kwargs["files"], data=kwargs["data"])
    assert response.status_code == 403


def test_admin_garbage_payload_is_a_422_not_a_500(admin_client):
    kwargs = _form("this is not json")
    response = admin_client.post(SAVE_PATH, files=kwargs["files"], data=kwargs["data"])
    assert response.status_code == 422


def test_admin_save_creates_candidate_and_resume(admin_client):
    kwargs = _form(_valid_parse())
    response = admin_client.post(
        SAVE_PATH,
        files=kwargs["files"],
        data={**kwargs["data"], "position_applied": "Senior Software Engineer"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["candidate_id"]
    assert body["resume_id"]

    # The save must be visible through the same API the screens read.
    candidate = admin_client.get(f"/api/candidates/{body['candidate_id']}")
    assert candidate.status_code == 200
    profile = candidate.json()
    assert profile["first_name"] == "Saved"
    assert profile["position_applied"] == "Senior Software Engineer"

    resumes = admin_client.get(f"/api/candidates/{body['candidate_id']}/resumes")
    assert resumes.status_code == 200
    assert any(r["id"] == body["resume_id"] for r in resumes.json()["resumes"])


def test_saving_the_same_email_twice_updates_not_duplicates(admin_client):
    kwargs = _form(_valid_parse())
    first = admin_client.post(SAVE_PATH, files=kwargs["files"], data=kwargs["data"])
    second = admin_client.post(SAVE_PATH, files=kwargs["files"], data=kwargs["data"])
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["candidate_id"] == second.json()["candidate_id"]
