"""Candidate status links (ATS Phase E).

The pinned property: the public payload carries the candidate's first name,
the job title and department, an application status label, and the stage
names with their candidate-facing descriptions. Nothing else. No score, no
email, no phone, no last name, no notes, no internal stage notes, and no
staff names. Same idea as test_traces_carry_no_contact_details.
"""
from __future__ import annotations

import json

from backend.models.models import Candidate
from backend.services import pipeline_service as ps
from backend.services import status_link_service as links
from backend.tests.phase_e_helpers import make_application, staff_client, staff_user

INTERNAL_NOTE = "Panel thought the SQL answer was weak"
ALLOWED_TOP = {"first_name", "job_title", "department", "status", "stages"}
ALLOWED_STAGE = {"name", "description", "state"}


def _banned_values(db_session, job, application, staff):
    candidate = db_session.get(Candidate, application.candidate_id)
    return [
        candidate.last_name,
        candidate.email,
        candidate.phone,
        "counter offer",  # candidate.notes
        INTERNAL_NOTE,
        job.hiring_manager,
        job.recruiter,
        staff.name,
        staff.email,
        "match_score",
        "score",
    ]


def _assert_allowlisted(payload: dict, banned: list[str]):
    assert set(payload) == ALLOWED_TOP
    for stage in payload["stages"]:
        assert set(stage) == ALLOWED_STAGE
    text = json.dumps(payload).lower()
    for value in banned:
        assert value and value.lower() not in text, f"public payload leaked {value!r}"


# --- service ---------------------------------------------------------------


def test_issue_link_is_unguessable_and_rotates(db_session):
    _, application = make_application(db_session)
    first = links.issue_link(db_session, application)
    second = links.issue_link(db_session, application)
    assert len(first) >= 32 and first != second
    assert links.find_by_token(db_session, first) is None
    assert links.find_by_token(db_session, second).id == application.id
    links.revoke_link(db_session, application)
    assert links.find_by_token(db_session, second) is None
    assert links.find_by_token(db_session, "") is None
    assert links.find_by_token(db_session, "x" * 500) is None


def test_public_view_shows_only_the_allowlist(db_session):
    job, application = make_application(db_session)
    staff = staff_user(db_session, "hiring_team", name="Ravi Panelist")
    ps.advance(db_session, application, actor_id=staff.id, note=INTERNAL_NOTE)

    view = links.public_view(db_session, application).model_dump()

    _assert_allowlisted(view, _banned_values(db_session, job, application, staff))
    assert view["first_name"] == "Mira"
    assert view["job_title"] == "Platform Engineer"
    assert view["department"] == "Engineering"
    assert view["status"] == "In progress"
    assert [s["state"] for s in view["stages"][:3]] == ["done", "current", "upcoming"]
    assert view["stages"][1]["description"].startswith("The hiring manager reviews")


def test_public_view_hides_skipped_rounds_and_unreached_outcomes(db_session):
    _, application = make_application(db_session)
    ps.skip(db_session, application)  # Resume submitted skipped
    names = [s.name for s in links.public_view(db_session, application).stages]
    assert "Resume submitted" not in names
    assert "Hired" not in names and "Offer declined" not in names


def test_rejected_application_reads_as_closed(db_session):
    _, application = make_application(db_session)
    ps.advance(db_session, application)
    ps.reject(db_session, application, note=INTERNAL_NOTE)
    view = links.public_view(db_session, application)
    assert view.status == "Closed"
    assert [s.state for s in view.stages] == ["done", "closed"]


# --- routes ----------------------------------------------------------------


def test_public_status_unknown_token_is_404(client):
    response = client.get("/api/public/status/not-a-real-token-000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "This status link is not active."


def test_status_link_lifecycle(admin_client, client, db_session):
    _, application = make_application(db_session)
    base = f"/api/applications/{application.id}/status-link"

    assert admin_client.get(base).json() == {"active": False, "path": None, "created_at": None}

    created = admin_client.post(base)
    # 200 with a path, not the transition router's "Unknown action" 404.
    assert created.status_code == 200, created.text
    first_path = created.json()["path"]
    assert first_path.startswith("/c/")
    token = first_path.removeprefix("/c/")
    assert client.get(f"/api/public/status/{token}").status_code == 200

    replaced = admin_client.post(base).json()["path"]
    assert replaced != first_path
    assert client.get(f"/api/public/status/{token}").status_code == 404

    revoked = admin_client.delete(base)
    assert revoked.status_code == 200 and revoked.json()["active"] is False
    assert client.get(f"/api/public/status/{replaced.removeprefix('/c/')}").status_code == 404


def test_status_link_permissions(demo_client, db_session, override_get_db):
    _, application = make_application(db_session)
    base = f"/api/applications/{application.id}/status-link"
    assert demo_client.post(base).status_code == 403
    assert demo_client.get(base).status_code == 403
    assert demo_client.delete(base).status_code == 403
    assert staff_client(db_session, "interviewer").post(base).status_code == 403
    assert staff_client(db_session, "hiring_team").post(base).status_code == 200


def test_candidate_view_matches_the_public_payload(admin_client, demo_client, client, db_session):
    _, application = make_application(db_session)
    preview = demo_client.get(f"/api/applications/{application.id}/candidate-view")
    assert preview.status_code == 200, preview.text
    path = admin_client.post(f"/api/applications/{application.id}/status-link").json()["path"]
    public = client.get(f"/api/public/status/{path.removeprefix('/c/')}")
    assert public.json() == preview.json()


def test_public_payload_over_http_carries_no_internal_details(admin_client, client, db_session):
    job, application = make_application(db_session)
    staff = staff_user(db_session, "hiring_team", name="Ravi Panelist")
    ps.advance(db_session, application, actor_id=staff.id, note=INTERNAL_NOTE)
    db_session.commit()
    path = admin_client.post(f"/api/applications/{application.id}/status-link").json()["path"]

    payload = client.get(f"/api/public/status/{path.removeprefix('/c/')}").json()

    _assert_allowlisted(payload, _banned_values(db_session, job, application, staff))
