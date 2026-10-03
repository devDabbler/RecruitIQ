"""Team management and personal settings (ATS Phase B)."""
from __future__ import annotations

from backend.models.models import User
from backend.tests.conftest import STAFF_PASSWORD


def _invite(client, email, role="hiring_team", name="New Person"):
    return client.post("/api/team/users", json={"email": email, "name": name, "role": role})


def test_list_excludes_the_demo_account_and_hides_emails_from_the_demo(admin_client, demo_client, staff_users):
    admin_view = admin_client.get("/api/team/users").json()["members"]
    assert all(m["role"] != "demo" for m in admin_view)
    assert all(m["email"] for m in admin_view)
    demo_view = demo_client.get("/api/team/users").json()["members"]
    assert demo_view and all(m["email"] is None for m in demo_view)


def test_a_hiring_manager_invites_and_the_temporary_password_works(hiring_manager_client, client, unique_email):
    response = _invite(hiring_manager_client, unique_email)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["member"]["role"] == "hiring_team"
    assert len(body["temporary_password"]) >= 12
    login = client.post("/auth/login", json={"email": unique_email, "password": body["temporary_password"]})
    assert login.status_code == 200
    assert login.json()["user"]["name"] == "New Person"


def test_only_an_admin_creates_an_admin(hiring_manager_client, admin_client, unique_email):
    assert _invite(hiring_manager_client, unique_email, role="admin").status_code == 403
    assert _invite(admin_client, unique_email, role="admin").status_code == 201


def test_hiring_team_cannot_invite_and_duplicates_are_409(hiring_team_client, admin_client, unique_email):
    assert _invite(hiring_team_client, unique_email).status_code == 403
    assert _invite(admin_client, unique_email).status_code == 201
    assert _invite(admin_client, unique_email.upper()).status_code == 409


def test_role_changes_are_admin_only_and_never_your_own(admin_client, hiring_manager_client, admin_user, unique_email):
    member = _invite(admin_client, unique_email).json()["member"]
    path = f"/api/team/users/{member['id']}/role"
    assert hiring_manager_client.put(path, json={"role": "interviewer"}).status_code == 403
    changed = admin_client.put(path, json={"role": "interviewer"})
    assert changed.status_code == 200 and changed.json()["role"] == "interviewer"
    assert admin_client.put(f"/api/team/users/{admin_user.id}/role", json={"role": "hiring_team"}).status_code == 409


def test_remove_refuses_people_with_feedback(admin_client, db_session, scoped_application, staff_users, unique_email):
    from backend.models.models import JobApplication
    from backend.services import feedback_service as fs
    from backend.services import pipeline_service as ps

    member = _invite(admin_client, unique_email, role="interviewer").json()["member"]
    person = db_session.get(User, member["id"])
    application = db_session.get(JobApplication, scoped_application["application_id"])
    interview = fs.assign(db_session, ps.current_stage(application), person)
    fs.submit_feedback(db_session, interview, person, 3, "hire", "")
    db_session.commit()

    refused = admin_client.delete(f"/api/team/users/{member['id']}")
    assert refused.status_code == 409
    assert "Change their role instead" in refused.json()["detail"]

    plain = _invite(admin_client, f"plain-{unique_email}").json()["member"]
    assert admin_client.delete(f"/api/team/users/{plain['id']}").status_code == 200
    assert db_session.get(User, plain["id"]) is None


def test_settings_name_timezone_and_password(staff_users, client):
    from backend.tests.conftest import _client_for

    person = staff_users["hiring_team"]
    me = _client_for(person)
    updated = me.put("/api/team/me", json={"name": "Renamed Person", "timezone": "America/Chicago"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["timezone"] == "America/Chicago"
    assert me.put("/api/team/me", json={"name": "X", "timezone": "Not a zone!"}).status_code == 422

    wrong = me.put("/api/team/me/password", json={"current_password": "nope", "new_password": "a-brand-new-password"})
    assert wrong.status_code == 400
    ok = me.put(
        "/api/team/me/password",
        json={"current_password": STAFF_PASSWORD, "new_password": "a-brand-new-password"},
    )
    assert ok.status_code == 200
    assert client.post("/auth/login", json={"email": person.email, "password": "a-brand-new-password"}).status_code == 200
    # Put it back for the rest of the session.
    me.put("/api/team/me/password", json={"current_password": "a-brand-new-password", "new_password": STAFF_PASSWORD})
    me.put("/api/team/me", json={"name": "Test Hiring Team"})


def test_demo_cannot_change_settings(demo_client):
    assert demo_client.put("/api/team/me", json={"name": "Hacker"}).status_code == 403


def test_auth_me_returns_the_name(hiring_manager_client):
    assert hiring_manager_client.get("/auth/me").json()["name"] == "Test Hiring Manager"


def test_interviewers_reach_their_settings(interviewer_client):
    assert interviewer_client.get("/api/team/me").status_code == 200
    # ...but not the team list, which their sidebar does not offer.
    assert interviewer_client.get("/api/team/users").status_code == 403


def test_jobs_link_to_team_members(admin_client, staff_users):
    payload = {
        "title": "Linked Job",
        "department": "Engineering",
        "job_overview": "Exists to test team links.",
        "required_qualifications": "Python",
        "hiring_manager_id": staff_users["hiring_manager"].id,
    }
    created = admin_client.post("/api/jobs/", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["hiring_manager_id"] == staff_users["hiring_manager"].id
    assert created.json()["recruiter_id"] is None

    ghost = "00000000-0000-4000-8000-00000000dead"
    bad = admin_client.post("/api/jobs/", json={**payload, "recruiter_id": ghost})
    assert bad.status_code == 422
    assert "someone on the team" in bad.json()["detail"]

    # An update that does not mention the links leaves them alone.
    job_id = created.json()["id"]
    without_links = {k: v for k, v in payload.items() if k != "hiring_manager_id"}
    kept = admin_client.put(f"/api/jobs/{job_id}", json={**without_links, "title": "Linked Job Renamed"})
    assert kept.status_code == 200, kept.text
    assert kept.json()["hiring_manager_id"] == staff_users["hiring_manager"].id
    admin_client.delete(f"/api/jobs/{job_id}")
