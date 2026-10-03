"""Bulk pipeline moves and the candidate CSV export (ATS Phase C)."""
from __future__ import annotations

import csv
import io

import pytest

from .conftest import SEED_EMAIL_DOMAIN
from .intake_helpers import client_for_role, job_with_applicants, unique


@pytest.fixture(scope="module")
def team_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "hiring_team")


@pytest.fixture(scope="module")
def fresh_interviewer_client(override_get_db, seed, db_session):
    """An interviewer assigned to nobody, unlike the session-wide one."""
    return client_for_role(db_session, "interviewer")


def _bulk(client, action, ids, note=None):
    return client.post(f"/api/applications/bulk/{action}", json={"application_ids": ids, "note": note})


def test_bulk_advance_moves_everyone(admin_client):
    _, _, app_ids = job_with_applicants(admin_client, 2)
    response = _bulk(admin_client, "advance", app_ids)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "action": "advance",
        "succeeded": 2,
        "failed": 0,
        "results": [
            {
                "application_id": app_id,
                "ok": True,
                "detail": None,
                "candidate_name": "Intake Test",
                "status": "active",
                "current_stage_key": "hm_review",
            }
            for app_id in app_ids
        ],
    }


def test_bulk_reports_each_failure_and_keeps_the_successes(admin_client):
    _, _, (a, b) = job_with_applicants(admin_client, 2)
    admin_client.post(f"/api/applications/{b}/reject", json={})
    body = _bulk(admin_client, "advance", [a, b, 99999999]).json()
    assert (body["succeeded"], body["failed"]) == (1, 2)
    by_id = {r["application_id"]: r for r in body["results"]}
    assert by_id[a]["ok"] is True
    assert "already rejected" in by_id[b]["detail"]
    assert by_id[99999999]["detail"] == "Application not found."
    # The success was committed despite the failures around it.
    assert admin_client.get(f"/api/applications/{a}").json()["current_stage_key"] == "hm_review"


def test_bulk_reject_records_the_reason(admin_client):
    _, _, app_ids = job_with_applicants(admin_client, 2)
    body = _bulk(admin_client, "reject", app_ids, note="Role filled internally.").json()
    assert body["succeeded"] == 2
    detail = admin_client.get(f"/api/applications/{app_ids[0]}").json()
    assert detail["status"] == "rejected"
    failed = next(s for s in detail["stages"] if s["status"] == "failed")
    assert failed["note"] == "Role filled internally."


def test_duplicate_ids_are_processed_once(admin_client):
    _, _, (a,) = job_with_applicants(admin_client, 1)
    body = _bulk(admin_client, "advance", [a, a]).json()
    assert body["succeeded"] == 1 and len(body["results"]) == 1


def test_only_advance_and_reject_exist_in_bulk(admin_client):
    _, _, (a,) = job_with_applicants(admin_client, 1)
    response = _bulk(admin_client, "skip", [a])
    # 404 from the bulk route, not a 422 from the single-application route
    # trying to read "bulk" as an id: proves the route order.
    assert response.status_code == 404
    assert "advance or reject" in response.json()["detail"]


@pytest.mark.parametrize("ids", [[], list(range(1, 102))])
def test_bulk_size_limits(admin_client, ids):
    assert _bulk(admin_client, "advance", ids).status_code == 422


def test_bulk_follows_the_permission_matrix(admin_client, demo_client, fresh_interviewer_client, team_client):
    _, _, (a,) = job_with_applicants(admin_client, 1)
    assert _bulk(demo_client, "advance", [a]).status_code == 403
    assert _bulk(fresh_interviewer_client, "advance", [a]).status_code == 403
    assert _bulk(team_client, "advance", [a]).status_code == 200


EXPECTED_HEADER = [
    "First name", "Last name", "Email", "Phone", "Location", "Current role",
    "Current company", "Source", "Status", "Tags", "Applications", "Added",
]


def _rows(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    return list(csv.reader(io.StringIO(response.text.lstrip("﻿"))))


def test_export_header_has_no_scores(client):
    header = _rows(client.get("/api/candidates/export.csv"))[0]
    assert header == EXPECTED_HEADER
    assert not any("score" in h.lower() or "match" in h.lower() for h in header)


def test_export_respects_the_job_filter(client, seed):
    rows = _rows(client.get(f"/api/candidates/export.csv?job_id={seed['job_id']}"))
    emails = {row[2] for row in rows[1:]}
    assert f"ada@{SEED_EMAIL_DOMAIN}" in emails
    assert f"alan@{SEED_EMAIL_DOMAIN}" not in emails


def test_export_lists_tags_and_applications(admin_client):
    job_id, (cid,), _ = job_with_applicants(admin_client, 1)
    admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "export-check"})
    email = admin_client.get(f"/api/candidates/{cid}").json()["email"]
    rows = _rows(admin_client.get(f"/api/candidates/export.csv?keyword={email}"))
    assert len(rows) == 2
    row = dict(zip(rows[0], rows[1]))
    assert row["Tags"] == "export-check"
    assert row["Applications"].endswith("(Resume submitted)")


def test_export_neutralizes_spreadsheet_formulas(admin_client):
    email = f"{unique('formula')}@{SEED_EMAIL_DOMAIN}"
    admin_client.post(
        "/api/candidates/",
        json={"first_name": '=HYPERLINK("http://x","y")', "last_name": "@risk", "email": email},
    )
    rows = _rows(admin_client.get(f"/api/candidates/export.csv?keyword={email}"))
    row = dict(zip(rows[0], rows[1]))
    assert row["First name"].startswith("'=")
    assert row["Last name"] == "'@risk"


def test_interviewer_export_contains_only_assigned_candidates(fresh_interviewer_client):
    rows = _rows(fresh_interviewer_client.get("/api/candidates/export.csv"))
    assert rows == [EXPECTED_HEADER]


def test_candidate_list_filters_by_job(client, seed):
    body = client.get(f"/api/candidates/?job_id={seed['job_id']}&page_size=100").json()
    ids = {c["id"] for c in body["results"]}
    assert seed["candidate_id"] in ids
    assert seed["candidate_ids"][2] not in ids
