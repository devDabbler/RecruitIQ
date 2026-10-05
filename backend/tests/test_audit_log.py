"""Audit log (pilot plan Track 1 #3).

Every staff request against candidate data leaves one row naming who, what,
which route and which candidate, with field names but never values. These
tests drive the real app through the shared rolled-back session from
conftest, then read audit_events directly.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import func, text
from sqlalchemy.exc import DBAPIError

from backend.main import app
from backend.models.models import AuditEvent, User
from backend.services import audit_service
from backend.utils.auth import create_access_token

from .conftest import SEED_EMAIL_DOMAIN, SEED_EPOCH
from .intake_helpers import application_id_for, new_candidate, new_job, unique

CANARY = "audit-canary-value-7f3e"


def _staff(db_session, role: str) -> tuple[TestClient, User]:
    user = User(
        email=f"{unique(role)}@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role=role,
        name=f"Audit {role}",
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


def _marker(db_session) -> int:
    return db_session.query(func.coalesce(func.max(AuditEvent.id), 0)).scalar()


def _events_since(db_session, marker: int, **filters) -> list[AuditEvent]:
    query = db_session.query(AuditEvent).filter(AuditEvent.id > marker)
    for key, value in filters.items():
        query = query.filter(getattr(AuditEvent, key) == value)
    return query.order_by(AuditEvent.id).all()


def _row_text(db_session, event_id: int) -> str:
    return db_session.execute(
        text("SELECT a::text FROM audit_events a WHERE id = :id"), {"id": event_id}
    ).scalar()


@pytest.fixture(scope="module")
def admin(override_get_db, seed, db_session):
    return _staff(db_session, "admin")


# --- classification ---------------------------------------------------------


def test_every_route_is_classified_exactly_once():
    """A new route must be listed in AUDITED_ROUTES or NOT_AUDITED.

    The same default-deny idea as the erasure table walk: forgetting a route
    fails CI instead of silently leaving it out of the log.
    """
    problems = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods):
            key = audit_service.endpoint_key(method, route.path)
            audited = [r for r in audit_service.AUDITED_ROUTES if r.pattern.fullmatch(key)]
            exempt = [p for p, _ in audit_service.NOT_AUDITED if p.fullmatch(key)]
            if bool(audited) + len(exempt) != 1:
                problems.append((key, len(audited), len(exempt)))
    assert problems == []


def test_candidate_routes_are_audited():
    for method, template in [
        ("GET", "/api/candidates/{candidate_id}"),
        ("PUT", "/api/candidates/{candidate_id}"),
        ("DELETE", "/api/candidates/{candidate_id}"),
        ("GET", "/api/candidates/export.csv"),
        ("POST", "/api/applications/{application_id}/{action}"),
        ("GET", "/api/resume/{resume_id}/view"),
        ("POST", "/api/assistant/chat"),
    ]:
        assert audit_service.rule_for(method, template) is not None, (method, template)
    assert audit_service.rule_for("GET", "/api/candidates/export.csv").action == "export"


# --- what gets written ------------------------------------------------------


def test_view_records_actor_candidate_and_route_template(db_session, admin, seed):
    client, user = admin
    marker = _marker(db_session)
    candidate_id = seed["candidate_id"]

    assert client.get(f"/api/candidates/{candidate_id}").status_code == 200

    (event,) = _events_since(db_session, marker, actor_id=user.id)
    assert event.action == "view"
    assert event.actor_role == "admin"
    assert event.subject_type == "candidate"
    assert event.subject_id == candidate_id
    assert event.candidate_id == candidate_id
    assert event.endpoint == "GET /api/candidates/{candidate_id}"
    assert event.status_code == 200
    assert event.fields is None


def test_update_records_field_names_never_values(db_session, admin):
    client, user = admin
    candidate_id = new_candidate(client)
    marker = _marker(db_session)

    response = client.put(f"/api/candidates/{candidate_id}", json={"headline": CANARY, "location": "Remote"})
    assert response.status_code == 200, response.text

    (event,) = _events_since(db_session, marker, actor_id=user.id)
    assert event.action == "update"
    assert event.fields == ["headline", "location"]
    assert CANARY not in _row_text(db_session, event.id)


def test_search_terms_never_reach_the_log(db_session, admin):
    client, user = admin
    marker = _marker(db_session)

    assert client.get("/api/candidates/", params={"search": CANARY}).status_code == 200

    (event,) = _events_since(db_session, marker, actor_id=user.id)
    assert event.endpoint == "GET /api/candidates/"
    assert CANARY not in _row_text(db_session, event.id)


def test_create_records_the_new_candidate(db_session, admin):
    client, user = admin
    marker = _marker(db_session)

    candidate_id = new_candidate(client)

    (event,) = _events_since(db_session, marker, actor_id=user.id)
    assert (event.action, event.subject_type) == ("create", "candidate")
    assert event.candidate_id == candidate_id
    assert event.subject_id == candidate_id


def test_erasure_is_recorded_and_the_event_outlives_the_candidate(db_session, admin):
    client, user = admin
    candidate_id = new_candidate(client)
    marker = _marker(db_session)

    assert client.delete(f"/api/candidates/{candidate_id}").status_code == 200

    (event,) = _events_since(db_session, marker, actor_id=user.id)
    assert (event.action, event.candidate_id, event.status_code) == ("delete", candidate_id, 200)
    # Still there after the erasure, and still holding nothing but ids.
    assert db_session.get(AuditEvent, event.id) is not None


def test_export_is_recorded_as_export(db_session, admin):
    client, user = admin
    marker = _marker(db_session)

    assert client.get("/api/candidates/export.csv").status_code == 200

    (event,) = _events_since(db_session, marker, actor_id=user.id)
    assert event.action == "export"


def test_application_events_resolve_the_candidate(db_session, admin):
    client, user = admin
    job_id = new_job(client, "Audit Job")
    candidate_id = new_candidate(client, job_id=job_id)
    application_id = application_id_for(client, candidate_id, job_id)
    marker = _marker(db_session)

    response = client.post(f"/api/applications/{application_id}/advance", json={})
    assert response.status_code == 200, response.text

    (event,) = _events_since(db_session, marker, actor_id=user.id)
    assert event.action == "update"
    assert event.subject_type == "application"
    assert event.subject_id == str(application_id)
    assert event.candidate_id == candidate_id
    assert event.detail == "advance"


def test_bulk_moves_write_one_event_per_application(db_session, admin):
    client, user = admin
    job_id = new_job(client, "Audit Bulk Job")
    people = [new_candidate(client, job_id=job_id) for _ in range(2)]
    applications = [application_id_for(client, cid, job_id) for cid in people]
    marker = _marker(db_session)

    response = client.post("/api/applications/bulk/advance", json={"application_ids": applications})
    assert response.status_code == 200, response.text

    events = _events_since(db_session, marker, actor_id=user.id)
    assert sorted(e.candidate_id for e in events) == sorted(people)
    assert {e.subject_id for e in events} == {str(a) for a in applications}


def test_refused_attempts_are_recorded(db_session, override_get_db, seed):
    team_client, team_user = _staff(db_session, "hiring_team")
    interviewer_client, interviewer = _staff(db_session, "interviewer")
    candidate_id = seed["candidate_ids"][2]
    marker = _marker(db_session)

    assert team_client.delete(f"/api/candidates/{candidate_id}").status_code == 403
    assert interviewer_client.get(f"/api/candidates/{candidate_id}").status_code == 404

    (denied_delete,) = _events_since(db_session, marker, actor_id=team_user.id)
    assert (denied_delete.action, denied_delete.status_code) == ("delete", 403)
    assert denied_delete.candidate_id == candidate_id
    (denied_view,) = _events_since(db_session, marker, actor_id=interviewer.id)
    assert (denied_view.action, denied_view.status_code) == ("view", 404)


def test_demo_and_anonymous_requests_are_not_recorded(db_session, client, demo_client, seed):
    marker = _marker(db_session)

    client.get(f"/api/candidates/{seed['candidate_id']}")
    demo_client.get(f"/api/candidates/{seed['candidate_id']}")
    demo_client.delete(f"/api/candidates/{seed['candidate_id']}")

    assert _events_since(db_session, marker) == []


def test_unaudited_routes_write_nothing(db_session, admin):
    client, _ = admin
    marker = _marker(db_session)

    assert client.get("/api/reports/dashboard").status_code == 200

    assert _events_since(db_session, marker) == []


def test_a_failed_audit_write_never_fails_the_request(db_session, admin, seed, monkeypatch):
    client, _ = admin

    def boom(*args, **kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(audit_service, "_write", boom)
    assert client.get(f"/api/candidates/{seed['candidate_id']}").status_code == 200


# --- the table itself -------------------------------------------------------


def test_audit_events_are_append_only(db_session, admin, seed):
    client, user = admin
    marker = _marker(db_session)
    client.get(f"/api/candidates/{seed['candidate_id']}")
    (event,) = _events_since(db_session, marker, actor_id=user.id)

    for statement in (
        "UPDATE audit_events SET action = 'view' WHERE id = :id",
        "DELETE FROM audit_events WHERE id = :id",
    ):
        savepoint = db_session.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            db_session.execute(text(statement), {"id": event.id})
        savepoint.rollback()

    # A deliberate maintenance job may prune. Rolled back here: SET LOCAL
    # lasts until the outer transaction ends, which in this suite is never.
    savepoint = db_session.begin_nested()
    db_session.execute(text("SELECT set_config('recruitiq.audit_maintenance', 'on', true)"))
    db_session.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": event.id})
    savepoint.rollback()
    assert db_session.execute(
        text("SELECT coalesce(current_setting('recruitiq.audit_maintenance', true), '')")
    ).scalar() != "on"
    assert db_session.get(AuditEvent, event.id) is not None


# --- reading it -------------------------------------------------------------


def test_admin_reads_one_candidates_history_newest_first(db_session, admin):
    client, user = admin
    candidate_id = new_candidate(client)
    client.get(f"/api/candidates/{candidate_id}")
    client.put(f"/api/candidates/{candidate_id}", json={"location": "Remote"})

    response = client.get("/api/audit-events", params={"candidate_id": candidate_id})
    assert response.status_code == 200, response.text
    events = response.json()["events"]
    assert [e["action"] for e in events] == ["update", "view", "create"]
    assert events[0]["actor_email"] == user.email
    assert events[0]["fields"] == ["location"]


def test_audit_reads_page_by_id(db_session, admin):
    client, _ = admin
    candidate_id = new_candidate(client)
    for _ in range(3):
        client.get(f"/api/candidates/{candidate_id}")

    first = client.get("/api/audit-events", params={"candidate_id": candidate_id, "limit": 2}).json()
    assert len(first["events"]) == 2
    assert first["next_before_id"] == first["events"][-1]["id"]
    rest = client.get(
        "/api/audit-events",
        params={"candidate_id": candidate_id, "limit": 2, "before_id": first["next_before_id"]},
    ).json()
    assert len(rest["events"]) == 2
    assert rest["next_before_id"] is None
    assert rest["events"][0]["id"] < first["events"][-1]["id"]


def test_reading_the_log_is_itself_recorded(db_session, admin):
    client, user = admin
    marker = _marker(db_session)

    client.get("/api/audit-events", params={"action": "delete"})

    (event,) = _events_since(db_session, marker, actor_id=user.id)
    assert (event.action, event.subject_type) == ("view", "audit")


def test_unknown_action_filter_is_refused(admin):
    client, _ = admin
    assert client.get("/api/audit-events", params={"action": "steal"}).status_code == 422


@pytest.mark.parametrize("role", ["hiring_manager", "hiring_team", "interviewer"])
def test_only_admins_read_the_log(db_session, override_get_db, seed, role):
    client, _ = _staff(db_session, role)
    assert client.get("/api/audit-events").status_code == 403


def test_demo_and_anonymous_cannot_read_the_log(client, demo_client):
    assert client.get("/api/audit-events").status_code == 401
    assert demo_client.get("/api/audit-events").status_code == 403


def test_a_failed_request_discards_only_its_own_uncommitted_work(db_session):
    """Work flushed before the request (a test fixture here) survives a
    failed request; work the failed request flushed itself does not."""
    earlier = User(email=f"{unique('kept')}@{SEED_EMAIL_DOMAIN}", role="interviewer", created_at=SEED_EPOCH)
    db_session.add(earlier)
    db_session.flush()

    start = db_session.info.get(audit_service._FLUSHES, 0)
    audit_service._discard_failed_work(db_session, start)
    assert db_session.get(User, earlier.id) is not None

    partial = User(email=f"{unique('partial')}@{SEED_EMAIL_DOMAIN}", role="interviewer", created_at=SEED_EPOCH)
    db_session.add(partial)
    db_session.flush()
    partial_id = partial.id
    audit_service._discard_failed_work(db_session, start)
    assert db_session.query(User).filter(User.id == partial_id).first() is None
