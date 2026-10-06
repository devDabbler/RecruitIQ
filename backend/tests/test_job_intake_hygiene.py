"""Track 2 Phase 3: requisition numbers, departments, sources, Withdraw.

Runs inside the session-wide rolled-back transaction from conftest. Jobs and
candidates are created through the API with unique names so nothing here
depends on what another module left behind.
"""
from __future__ import annotations

import csv
import io

import pytest

from backend.models.models import Department, JobApplication
from backend.services import department_service, sources
from backend.services import pipeline_service as ps
from backend.services import reports_service as rs

from .intake_helpers import (
    JOB_PAYLOAD,
    application_id_for,
    client_for_role,
    new_candidate,
    new_job,
    unique,
)


def _job_body(**overrides) -> dict:
    return {**JOB_PAYLOAD, "title": f"Hygiene Job {unique('h')}", **overrides}


def _department(db_session, name: str, active: bool = True) -> Department:
    department = Department(name=name, active=active)
    db_session.add(department)
    db_session.commit()
    return department


# --- requisition numbers ----------------------------------------------------


def test_requisition_number_is_stored_trimmed_and_returned(admin_client):
    number = f"R-{unique('req')}"
    created = admin_client.post("/api/jobs/", json=_job_body(requisition_number=f"  {number} "))
    assert created.status_code == 201, created.text
    assert created.json()["requisition_number"] == number
    assert admin_client.get(f"/api/jobs/{created.json()['id']}").json()["requisition_number"] == number


def test_blank_requisition_number_is_stored_as_null(admin_client):
    created = admin_client.post("/api/jobs/", json=_job_body(requisition_number="   "))
    assert created.status_code == 201, created.text
    assert created.json()["requisition_number"] is None


def test_requisition_number_is_unique_when_set(admin_client):
    number = f"R-{unique('dup')}"
    first = admin_client.post("/api/jobs/", json=_job_body(requisition_number=number)).json()
    clash = admin_client.post("/api/jobs/", json=_job_body(requisition_number=number))
    assert clash.status_code == 409
    assert first["title"] in clash.json()["detail"]

    second = admin_client.post("/api/jobs/", json=_job_body()).json()
    moved = admin_client.put(f"/api/jobs/{second['id']}", json={**_job_body(), "requisition_number": number})
    assert moved.status_code == 409

    # A job may keep its own number on save, and many jobs may have none.
    kept = admin_client.put(f"/api/jobs/{first['id']}", json={**_job_body(), "requisition_number": number})
    assert kept.status_code == 200, kept.text
    assert admin_client.post("/api/jobs/", json=_job_body()).status_code == 201


def test_requisition_number_is_limited_to_40_characters(admin_client):
    assert admin_client.post("/api/jobs/", json=_job_body(requisition_number="R" * 41)).status_code == 422


def test_job_search_finds_a_job_by_requisition_number(admin_client):
    number = f"WD-{unique('find')}"
    job = admin_client.post("/api/jobs/", json=_job_body(requisition_number=number)).json()
    found = admin_client.get("/api/jobs/", params={"keyword": number.lower()}).json()
    assert [row["id"] for row in found["results"]] == [job["id"]]


def test_candidate_csv_names_the_requisition(admin_client):
    number = f"R-{unique('csv')}"
    job = admin_client.post("/api/jobs/", json=_job_body(requisition_number=number)).json()
    new_candidate(admin_client, job_id=job["id"])
    response = admin_client.get("/api/candidates/export.csv", params={"job_id": job["id"]})
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.text.lstrip("ï»¿"))))
    applications = rows[1][rows[0].index("Applications")]
    assert f"{job['title']} [{number}] (Resume submitted)" in applications


# --- departments ------------------------------------------------------------


def test_job_department_must_be_on_the_list(admin_client):
    refused = admin_client.post("/api/jobs/", json=_job_body(department=f"Nowhere {unique('d')}"))
    assert refused.status_code == 422
    assert "department list" in refused.json()["detail"]


def test_job_department_is_matched_ignoring_case_and_stored_canonically(admin_client):
    created = admin_client.post("/api/jobs/", json=_job_body(department="  engineering "))
    assert created.status_code == 201, created.text
    assert created.json()["department"] == "Engineering"


def test_turned_off_department_is_refused_for_new_jobs_but_kept_on_old_ones(admin_client, db_session):
    name = f"Legacy {unique('d')}"
    department = _department(db_session, name)
    job = admin_client.post("/api/jobs/", json=_job_body(department=name)).json()

    department.active = False
    db_session.commit()

    assert admin_client.post("/api/jobs/", json=_job_body(department=name)).status_code == 422
    kept = admin_client.put(f"/api/jobs/{job['id']}", json={**_job_body(department=name), "title": job["title"]})
    assert kept.status_code == 200, kept.text


def test_list_hides_turned_off_departments_unless_asked(admin_client, db_session):
    on = _department(db_session, f"On {unique('d')}")
    off = _department(db_session, f"Off {unique('d')}", active=False)
    names = {d["name"] for d in admin_client.get("/api/departments").json()["departments"]}
    assert on.name in names and off.name not in names
    everything = admin_client.get("/api/departments", params={"include_inactive": True}).json()["departments"]
    assert off.name in {d["name"] for d in everything}


def test_admin_adds_a_department_and_duplicates_are_refused(admin_client):
    name = f"Finance {unique('d')}"
    created = admin_client.post("/api/departments", json={"name": f"  {name}  "})
    assert created.status_code == 201, created.text
    assert created.json() == {**created.json(), "name": name, "active": True, "job_count": 0}
    assert admin_client.post("/api/departments", json={"name": name.upper()}).status_code == 409
    assert admin_client.post("/api/departments", json={"name": "   "}).status_code == 422


def test_rename_moves_the_departments_jobs_in_the_same_transaction(admin_client, db_session):
    old = f"Ops {unique('d')}"
    department = _department(db_session, old)
    job = admin_client.post("/api/jobs/", json=_job_body(department=old)).json()

    new = f"Operations {unique('d')}"
    renamed = admin_client.put(f"/api/departments/{department.id}", json={"name": new})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["jobs_renamed"] == 1
    assert renamed.json()["department"]["job_count"] == 1
    assert admin_client.get(f"/api/jobs/{job['id']}").json()["department"] == new


def test_rename_onto_another_departments_name_is_refused(admin_client, db_session):
    a = _department(db_session, f"Alpha {unique('d')}")
    b = _department(db_session, f"Beta {unique('d')}")
    assert admin_client.put(f"/api/departments/{a.id}", json={"name": b.name.lower()}).status_code == 409
    assert admin_client.put("/api/departments/99999999", json={"active": False}).status_code == 404


def test_only_an_admin_manages_departments(db_session, demo_client, override_get_db, seed):
    department = _department(db_session, f"Locked {unique('d')}")
    for role in ("hiring_manager", "hiring_team", "interviewer"):
        client = client_for_role(db_session, role)
        assert client.post("/api/departments", json={"name": unique("x")}).status_code == 403, role
        assert client.put(f"/api/departments/{department.id}", json={"active": False}).status_code == 403, role
    assert demo_client.post("/api/departments", json={"name": unique("x")}).status_code == 403
    # Anyone who builds jobs can read the list; so can the public demo.
    assert client_for_role(db_session, "hiring_manager").get("/api/departments").status_code == 200
    assert demo_client.get("/api/departments").status_code == 200


def test_validate_for_job_messages_are_plain_english(db_session, seed):
    with pytest.raises(department_service.DepartmentError) as missing:
        department_service.validate_for_job(db_session, "")
    assert missing.value.detail == "A department is required."
    with pytest.raises(department_service.DepartmentError) as unknown:
        department_service.validate_for_job(db_session, f"Nope {unique('d')}")
    assert "ask an admin" in unknown.value.detail


# --- sources ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("linkedin", "linkedin"),
        ("  LinkedIn ", "linkedin"),
        ("internal", "internal"),
        ("direct", "direct_application"),
        ("resume_upload", "direct_application"),
        ("billboard", "other"),
        (None, "direct_application"),
        ("", "direct_application"),
    ],
)
def test_normalize_maps_into_the_one_vocabulary(raw, stored):
    assert sources.normalize(raw) == stored


def test_vocabulary_is_the_candidate_sources_plus_internal():
    from backend.models.candidate import ApplicationSource, CandidateSource

    assert set(sources.APPLICATION_SOURCES) == {s.value for s in ApplicationSource}
    assert set(sources.APPLICATION_SOURCES) == {s.value for s in CandidateSource} | {"internal"}


def test_labels_cover_unknown_and_unrecorded():
    assert sources.label("company_website") == "Company website"
    assert sources.label(None) == "Not recorded"
    assert sources.label("unknown") == "Not recorded"
    assert sources.label("billboard") == "Other"


def test_add_candidate_records_the_chosen_source_on_the_application(admin_client):
    job_id = new_job(admin_client)
    candidate_id = new_candidate(admin_client, job_id=job_id, source="referral")
    rows = admin_client.get(f"/api/jobs/applications/{candidate_id}").json()
    assert [row["source"] for row in rows if row["job_id"] == job_id] == ["referral"]


def test_add_candidate_without_a_source_applied_directly(admin_client):
    job_id = new_job(admin_client)
    candidate_id = new_candidate(admin_client, job_id=job_id)
    rows = admin_client.get(f"/api/jobs/applications/{candidate_id}").json()
    assert [row["source"] for row in rows if row["job_id"] == job_id] == ["direct_application"]


def test_consider_for_role_takes_internal_and_refuses_free_text(admin_client):
    candidate_id = new_candidate(admin_client)
    job_id = new_job(admin_client)
    bad = admin_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": candidate_id, "source": "direct"})
    assert bad.status_code == 422
    ok = admin_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": candidate_id, "source": "internal"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["source"] == "internal"


def test_source_mix_carries_labels(db_session, seed):
    rows = rs.source_mix(db_session, rs.Scope.of())
    assert rows, "the seeded application has a source"
    assert all(row["label"] == sources.label(row["source"]) for row in rows)


def test_department_mix_groups_applications_by_department(admin_client, db_session, seed):
    name = f"Mix {unique('d')}"
    _department(db_session, name)
    job = admin_client.post("/api/jobs/", json=_job_body(department=name)).json()
    new_candidate(admin_client, job_id=job["id"])
    new_candidate(admin_client, job_id=job["id"])
    rows = {row["department"]: row for row in rs.department_mix(db_session, rs.Scope.of())}
    assert rows[name] == {"department": name, "jobs": 1, "applications": 2, "hired": 0}
    report = admin_client.get("/api/reports/summary").json()
    assert name in {row["department"] for row in report["department_mix"]}


# --- withdraw ---------------------------------------------------------------


def _fresh_application(admin_client) -> tuple[int, str, int]:
    job_id = new_job(admin_client)
    candidate_id = new_candidate(admin_client, job_id=job_id)
    return job_id, candidate_id, application_id_for(admin_client, candidate_id, job_id)


def test_withdraw_from_any_active_stage(admin_client):
    _job_id, candidate_id, application_id = _fresh_application(admin_client)
    assert admin_client.post(f"/api/applications/{application_id}/advance", json={}).status_code == 200

    response = admin_client.post(
        f"/api/applications/{application_id}/withdraw", json={"note": "Took another offer."}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "withdrawn"
    assert body["current_stage_key"] is None
    by_key = {s["key"]: s for s in body["stages"]}
    assert by_key["resume_submitted"]["status"] == "passed"
    assert by_key["hm_review"]["status"] == "skipped"
    assert by_key["hm_review"]["note"] == "Took another offer."
    assert by_key["withdrawn"]["status"] == "passed"
    assert by_key["hired"]["status"] == "skipped"
    assert all(s["status"] != "pending" for s in body["stages"])
    assert admin_client.get(f"/api/candidates/{candidate_id}").json()["status"] == "withdrawn"


def test_withdraw_is_refused_once_the_application_has_ended(admin_client):
    _job_id, _candidate_id, application_id = _fresh_application(admin_client)
    assert admin_client.post(f"/api/applications/{application_id}/reject", json={}).status_code == 200
    again = admin_client.post(f"/api/applications/{application_id}/withdraw", json={})
    assert again.status_code == 409


def test_withdraw_needs_pipeline_move(db_session, demo_client, override_get_db, seed, admin_client):
    _job_id, _candidate_id, application_id = _fresh_application(admin_client)
    assert demo_client.post(f"/api/applications/{application_id}/withdraw", json={}).status_code == 403
    interviewer = client_for_role(db_session, "interviewer")
    assert interviewer.post(f"/api/applications/{application_id}/withdraw", json={}).status_code in (403, 404)
    team = client_for_role(db_session, "hiring_team")
    assert team.post(f"/api/applications/{application_id}/withdraw", json={}).status_code == 200


def test_board_counts_withdrawn_outcomes(admin_client):
    job_id, _candidate_id, application_id = _fresh_application(admin_client)
    admin_client.post(f"/api/applications/{application_id}/withdraw", json={})
    board = admin_client.get(f"/api/jobs/{job_id}/pipeline").json()
    assert board["outcomes"]["withdrawn"] == 1
    assert sum(len(c["applications"]) for c in board["columns"]) == 0


def test_withdrawal_reads_as_one_event_in_the_activity_feed(admin_client, db_session):
    job_id, _candidate_id, application_id = _fresh_application(admin_client)
    admin_client.post(f"/api/applications/{application_id}/withdraw", json={})
    events = rs.activity(db_session, rs.Scope.of(job_id=job_id))
    assert [e["kind"] for e in events] == ["withdrew", "applied"]


def test_new_outcome_stage_on_a_finished_application_is_skipped(db_session, seed, admin_client):
    """An application that ended before the Withdrawn stage existed gets it as skipped."""
    job_id, _candidate_id, application_id = _fresh_application(admin_client)
    admin_client.post(f"/api/applications/{application_id}/reject", json={})
    application = db_session.get(JobApplication, application_id)
    withdrawn_row = next(r for r in application.stages if r.stage.key == "withdrawn")
    db_session.delete(withdrawn_row)
    db_session.commit()
    db_session.expire(application)

    rows = ps.ensure_application_stages(db_session, db_session.get(JobApplication, application_id))
    restored = next(r for r in rows if r.stage.key == "withdrawn")
    assert restored.status == ps.SKIPPED
    assert restored.completed_at is not None
    db_session.commit()


def test_withdrawn_is_the_last_default_outcome():
    keys = [key for key, *_ in ps.DEFAULT_STAGES]
    assert keys[-1] == "withdrawn"
    assert ps.DEFAULT_STAGES[-1][2] == ps.OUTCOME
    assert "withdraw" in ps.ACTIONS
