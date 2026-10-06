"""Tags in candidate lists: filter, column, bulk tag (Track 2 Phase 5)."""
from __future__ import annotations

import csv
import io

import pytest

from backend.models.models import AuditEvent

from .intake_helpers import client_for_role, new_candidate, unique


@pytest.fixture(scope="module")
def team_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "hiring_team")


@pytest.fixture(scope="module")
def fresh_interviewer_client(override_get_db, seed, db_session):
    """An interviewer assigned to nobody."""
    return client_for_role(db_session, "interviewer")


def _tag(client, cid, tag):
    response = client.post(f"/api/candidates/{cid}/tags", json={"tag": tag})
    assert response.status_code == 200, response.text


def _bulk(client, ids, tag):
    return client.post("/api/candidates/bulk/tag", json={"candidate_ids": ids, "tag": tag})


def _listed(client, **params):
    response = client.get("/api/candidates/", params={"page_size": 100, **params})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="module")
def tagged(admin_client):
    """Three candidates: a has both tags, b has only the first, c has neither."""
    first, second = unique("phase5-first"), unique("phase5-second")
    a, b, c = (new_candidate(admin_client) for _ in range(3))
    _tag(admin_client, a, first)
    _tag(admin_client, a, second)
    _tag(admin_client, b, first)
    return {"a": a, "b": b, "c": c, "first": first, "second": second}


def test_filter_by_one_tag(admin_client, tagged):
    body = _listed(admin_client, tag=tagged["first"])
    assert {r["id"] for r in body["results"]} == {tagged["a"], tagged["b"]}
    assert body["total"] == 2


def test_every_tag_must_match(admin_client, tagged):
    body = _listed(admin_client, tag=[tagged["first"], tagged["second"]])
    assert [r["id"] for r in body["results"]] == [tagged["a"]]


def test_filter_tags_are_normalized(admin_client, tagged):
    # Typed the way a person would; stored lower-kebab-case.
    shouted = tagged["first"].upper().replace("-", " ")
    assert {r["id"] for r in _listed(admin_client, tag=shouted)["results"]} == {tagged["a"], tagged["b"]}


def test_a_tag_with_nothing_usable_is_a_422(admin_client):
    response = admin_client.get("/api/candidates/", params={"tag": "!!!"})
    assert response.status_code == 422
    assert "letter or number" in response.json()["detail"]


def test_list_rows_carry_their_tags(admin_client, tagged):
    rows = {r["id"]: r for r in _listed(admin_client, tag=tagged["first"])["results"]}
    assert rows[tagged["a"]]["tags"] == sorted([tagged["first"], tagged["second"]])
    assert rows[tagged["b"]]["tags"] == [tagged["first"]]


def test_export_uses_the_same_tag_filter(admin_client, tagged):
    response = admin_client.get(
        "/api/candidates/export.csv", params={"tag": [tagged["first"], tagged["second"]]}
    )
    assert response.status_code == 200, response.text
    rows = list(csv.reader(io.StringIO(response.text.lstrip("﻿"))))
    assert len(rows) == 2
    row = dict(zip(rows[0], rows[1]))
    assert row["Tags"] == "; ".join(sorted([tagged["first"], tagged["second"]]))


def test_bulk_tag_tags_everyone_and_counts_existing_as_done(admin_client, tagged):
    tag = unique("phase5-bulk")
    _tag(admin_client, tagged["c"], tag)
    response = _bulk(admin_client, [tagged["a"], tagged["b"], tagged["c"], tagged["a"]], tag.upper())
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["tag"], body["succeeded"], body["failed"]) == (tag, 3, 0)
    # Duplicates are processed once, in the order given.
    assert [r["candidate_id"] for r in body["results"]] == [tagged["a"], tagged["b"], tagged["c"]]
    assert all(r["candidate_name"] == "Intake Test" for r in body["results"])
    assert {r["id"] for r in _listed(admin_client, tag=tag)["results"]} == {
        tagged["a"],
        tagged["b"],
        tagged["c"],
    }


def test_bulk_tag_reports_each_failure_and_keeps_the_successes(admin_client):
    full, fine = new_candidate(admin_client), new_candidate(admin_client)
    for i in range(20):
        _tag(admin_client, full, f"cap{i}")
    missing = "00000000-0000-4000-8000-00000000dead"
    tag = unique("phase5-partial")
    body = _bulk(admin_client, [full, fine, missing], tag).json()
    assert (body["succeeded"], body["failed"]) == (1, 2)
    by_id = {r["candidate_id"]: r for r in body["results"]}
    assert by_id[fine]["ok"] is True
    assert "at most 20" in by_id[full]["detail"]
    assert by_id[missing]["detail"] == "Candidate not found."
    assert admin_client.get(f"/api/candidates/{fine}/tags").json()["tags"] == [tag]
    assert tag not in admin_client.get(f"/api/candidates/{full}/tags").json()["tags"]


def test_bulk_tag_refuses_an_empty_tag(admin_client):
    cid = new_candidate(admin_client)
    response = _bulk(admin_client, [cid], "   ")
    assert response.status_code == 422
    assert "letter or number" in response.json()["detail"]


@pytest.mark.parametrize("count", [0, 101])
def test_bulk_tag_size_limits(admin_client, count):
    ids = [f"00000000-0000-4000-8000-{i:012d}" for i in range(count)]
    assert _bulk(admin_client, ids, "x").status_code == 422


def test_bulk_tag_follows_the_permission_matrix(admin_client, demo_client, fresh_interviewer_client, team_client):
    cid = new_candidate(admin_client)
    assert _bulk(demo_client, [cid], "x").status_code == 403
    assert _bulk(fresh_interviewer_client, [cid], "x").status_code == 403
    assert _bulk(team_client, [cid], "x").status_code == 200


def test_bulk_tag_writes_one_audit_event_per_candidate(admin_client, db_session):
    a, b = new_candidate(admin_client), new_candidate(admin_client)
    assert _bulk(admin_client, [a, b], unique("phase5-audit")).status_code == 200
    db_session.expire_all()
    events = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.endpoint == "POST /api/candidates/bulk/tag", AuditEvent.candidate_id.in_([a, b]))
        .all()
    )
    assert {e.candidate_id for e in events} == {a, b}
    assert {(e.subject_type, e.action) for e in events} == {("candidate", "update")}
