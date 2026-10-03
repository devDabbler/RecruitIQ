"""Notes and tags on candidates (ATS Phase C).

Runs against the real schema inside the session-wide rolled-back transaction
from conftest. Writes go through the API wherever a route exists, so the
permission gate and the visibility filter are exercised with the data.
"""
from __future__ import annotations

import pytest

from backend.models.models import CandidateTag, Note
from backend.services.feedback_service import display_name
from backend.utils.tags import normalize_tag

from .intake_helpers import client_for_role, new_candidate, new_job


def test_models_import_and_map():
    assert Note.__tablename__ == "notes"
    assert CandidateTag.__tablename__ == "candidate_tags"
    assert {"author", "application", "stage"} <= set(Note.__mapper__.relationships.keys())


# The web mirror in web/src/lib/intake.test.ts pins the same table.
TAG_CASES = [
    ("Relocation OK", "relocation-ok"),
    ("  strong   SQL!! ", "strong-sql"),
    ("C++", "cplusplus"),
    ("C# developer", "csharp-developer"),
    ("Señor engineer", "senor-engineer"),
    ("already-kebab", "already-kebab"),
    ("--x--", "x"),
    ("a" * 80, "a" * 50),
]


@pytest.mark.parametrize("raw, expected", TAG_CASES)
def test_normalize_tag(raw, expected):
    assert normalize_tag(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "!!!", "---"])
def test_normalize_tag_refuses_nothing_left(raw):
    with pytest.raises(ValueError, match="letter or number"):
        normalize_tag(raw)


@pytest.fixture(scope="module")
def team_client(override_get_db, seed, db_session):
    return client_for_role(db_session, "hiring_team")


@pytest.fixture(scope="module")
def fresh_interviewer_client(override_get_db, seed, db_session):
    """An interviewer assigned to nobody, unlike the session-wide one."""
    return client_for_role(db_session, "interviewer")


def test_add_tag_normalizes_dedupes_and_removes(admin_client):
    cid = new_candidate(admin_client)
    first = admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "Relocation OK"})
    assert first.status_code == 200, first.text
    assert first.json() == {"candidate_id": cid, "tags": ["relocation-ok"]}

    again = admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "relocation ok"})
    assert again.json()["tags"] == ["relocation-ok"]

    admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "Strong SQL"})
    listed = admin_client.get(f"/api/candidates/{cid}/tags")
    assert listed.json()["tags"] == ["relocation-ok", "strong-sql"]  # alphabetical

    removed = admin_client.delete(f"/api/candidates/{cid}/tags/relocation-ok")
    assert removed.status_code == 200
    assert removed.json()["tags"] == ["strong-sql"]
    # Idempotent: removing it twice is not an error.
    assert admin_client.delete(f"/api/candidates/{cid}/tags/relocation-ok").status_code == 200


def test_empty_tag_is_a_422_with_a_reason(admin_client):
    cid = new_candidate(admin_client)
    response = admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "!!!"})
    assert response.status_code == 422
    assert "letter or number" in response.json()["detail"]


def test_tag_limit_is_twenty(admin_client):
    cid = new_candidate(admin_client)
    for i in range(20):
        assert admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": f"t{i}"}).status_code == 200
    response = admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "one-too-many"})
    assert response.status_code == 409
    assert "at most 20" in response.json()["detail"]
    # Re-adding an existing tag at the limit is still fine.
    assert admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "t3"}).status_code == 200


def test_unknown_candidate_tags_is_404(admin_client):
    assert admin_client.get("/api/candidates/00000000-0000-4000-8000-00000000dead/tags").status_code == 404


def test_tag_counts_cover_every_candidate(admin_client, client):
    a = new_candidate(admin_client)
    b = new_candidate(admin_client)
    tag = "phase-c-count-check"
    admin_client.post(f"/api/candidates/{a}/tags", json={"tag": tag})
    admin_client.post(f"/api/candidates/{b}/tags", json={"tag": tag})
    counts = {row["tag"]: row["count"] for row in client.get("/api/tags").json()}
    assert counts[tag] == 2


def test_tag_writes_follow_the_permission_matrix(demo_client, team_client, fresh_interviewer_client, admin_client):
    cid = new_candidate(admin_client)
    path = f"/api/candidates/{cid}/tags"
    assert demo_client.post(path, json={"tag": "x"}).status_code == 403
    assert fresh_interviewer_client.post(path, json={"tag": "x"}).status_code == 403
    assert team_client.post(path, json={"tag": "x"}).status_code == 200
    assert fresh_interviewer_client.delete(f"{path}/x").status_code == 403
    assert team_client.delete(f"{path}/x").status_code == 200


def test_interviewer_cannot_read_tags_of_unassigned_candidates(admin_client, fresh_interviewer_client):
    cid = new_candidate(admin_client)
    assert fresh_interviewer_client.get(f"/api/candidates/{cid}/tags").status_code == 404
    assert fresh_interviewer_client.get("/api/tags").json() == []


def test_general_note_round_trips_with_the_author(admin_client, admin_user):
    cid = new_candidate(admin_client)
    created = admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "  Great call.  "})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["body"] == "Great call."
    assert body["author_name"] == display_name(admin_user)
    assert "@" not in body["author_name"]  # never an email, even for a nameless admin
    assert body["application_id"] is None and body["stage_name"] is None


def test_notes_are_newest_first(admin_client):
    cid = new_candidate(admin_client)
    admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "first"})
    admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "second"})
    listed = admin_client.get(f"/api/candidates/{cid}/notes").json()
    assert [n["body"] for n in listed] == ["second", "first"]


def test_stage_note_carries_job_and_stage_labels(admin_client, seed):
    response = admin_client.post(
        f"/api/candidates/{seed['candidate_id']}/notes",
        json={"body": "Asked about SQL depth.", "application_id": seed["application_id"], "stage_key": "hm_review"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["job_title"] == "Senior Data Engineer"
    assert response.json()["stage_name"] == "Hiring manager review"


@pytest.mark.parametrize(
    "payload, fragment",
    [
        ({"body": "   "}, "some text"),
        ({"body": "x", "stage_key": "hm_review"}, "Pick the application"),
        ({"body": "x", "application_id": -1}, "different candidate"),
    ],
)
def test_bad_notes_are_422_with_a_reason(admin_client, payload, fragment):
    cid = new_candidate(admin_client)
    response = admin_client.post(f"/api/candidates/{cid}/notes", json=payload)
    assert response.status_code == 422
    assert fragment in str(response.json()["detail"])


def test_application_of_another_candidate_is_refused(admin_client, seed):
    other = new_candidate(admin_client)
    response = admin_client.post(
        f"/api/candidates/{other}/notes",
        json={"body": "x", "application_id": seed["application_id"]},
    )
    assert response.status_code == 422


def test_unknown_stage_key_is_refused(admin_client, seed):
    response = admin_client.post(
        f"/api/candidates/{seed['candidate_id']}/notes",
        json={"body": "x", "application_id": seed["application_id"], "stage_key": "lunch"},
    )
    assert response.status_code == 422
    assert "lunch" in response.json()["detail"]


def test_imported_notes_have_no_author(admin_client, db_session):
    cid = new_candidate(admin_client)
    db_session.add(Note(candidate_id=cid, author_id=None, body="From the old notes field."))
    db_session.commit()
    listed = admin_client.get(f"/api/candidates/{cid}/notes").json()
    assert listed[0]["author_name"] is None


def test_note_writes_follow_the_permission_matrix(demo_client, team_client, fresh_interviewer_client, admin_client):
    cid = new_candidate(admin_client)
    path = f"/api/candidates/{cid}/notes"
    assert demo_client.post(path, json={"body": "x"}).status_code == 403
    assert fresh_interviewer_client.post(path, json={"body": "x"}).status_code == 403
    assert team_client.post(path, json={"body": "x"}).status_code == 201


def test_interviewer_cannot_read_notes_of_unassigned_candidates(admin_client, fresh_interviewer_client):
    cid = new_candidate(admin_client)
    admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "private"})
    assert fresh_interviewer_client.get(f"/api/candidates/{cid}/notes").status_code == 404


def test_deleting_a_job_keeps_the_note_without_its_label(admin_client, db_session, seed):
    job_id = new_job(admin_client, "Note Survives")
    cid = new_candidate(admin_client)
    applied = admin_client.post(f"/api/jobs/{job_id}/apply", json={"candidate_id": cid})
    application_id = applied.json()["id"]
    admin_client.post(
        f"/api/candidates/{cid}/notes",
        json={"body": "Stage note.", "application_id": application_id, "stage_key": "resume_submitted"},
    )
    assert admin_client.delete(f"/api/jobs/{job_id}").status_code == 200
    db_session.expire_all()
    listed = admin_client.get(f"/api/candidates/{cid}/notes").json()
    assert listed[0]["body"] == "Stage note."
    assert listed[0]["application_id"] is None and listed[0]["job_title"] is None


def test_deleting_a_candidate_removes_their_notes_and_tags(admin_client, db_session):
    cid = new_candidate(admin_client)
    admin_client.post(f"/api/candidates/{cid}/notes", json={"body": "bye"})
    admin_client.post(f"/api/candidates/{cid}/tags", json={"tag": "bye"})
    assert admin_client.delete(f"/api/candidates/{cid}").status_code == 200
    db_session.expire_all()
    assert db_session.query(Note).filter(Note.candidate_id == cid).count() == 0
    assert db_session.query(CandidateTag).filter(CandidateTag.candidate_id == cid).count() == 0
