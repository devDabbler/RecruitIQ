"""Candidate data export (pilot plan Track 1 #5).

A data access request gets everything held about one person: every row the
erasure would delete, the names those rows refer to, and who has accessed
the record. Administrators only, and every download lands in the audit log.
"""
from __future__ import annotations

from sqlalchemy import text

from backend.models.models import AuditEvent
from backend.services import data_export_service as ds
from backend.services import erasure_service as es

# `storage` is a fixture; importing it registers it for this module.
from .test_candidate_erasure import _candidate, _full_candidate, _job, storage  # noqa: F401

SECRET_TOKEN = "export-test-status-token-9c41"


def test_export_reads_every_table_the_erasure_deletes():
    """Anything a deletion would remove, an export must show, and the reverse."""
    assert {table for table, _ in ds.EXPORT_STEPS} == es.ERASED_TABLES
    assert set(ds.SECTION_LABELS) == es.ERASED_TABLES


def _cleanup(db_session, storage, candidate_ids, job):
    for cid in candidate_ids:
        es.erase_candidate(db_session, cid, storage=storage, redis_client=_NoRedis())
    db_session.execute(text("DELETE FROM pipeline_stages WHERE job_id = :j"), {"j": job.id})
    db_session.execute(text("DELETE FROM jobs WHERE id = :j"), {"j": job.id})
    db_session.commit()


class _NoRedis:
    def scan_iter(self, match):
        return []

    def delete(self, *keys):
        return 0


def test_export_holds_everything_and_nothing_else(db_session, admin_client, staff_users, storage):
    job = _job(db_session, "Data Export Test Engineer")
    target = _full_candidate(db_session, storage, staff_users, job)
    cid = target["candidate_id"]
    bystander = _candidate(db_session, "bystander")
    db_session.execute(
        text("UPDATE job_applications SET public_token = :t WHERE id = :a"),
        {"t": SECRET_TOKEN, "a": target["application_id"]},
    )
    db_session.commit()
    bystander_email = db_session.execute(
        text("SELECT email FROM candidates WHERE id = :c"), {"c": bystander}
    ).scalar_one()

    try:
        resp = admin_client.get(f"/api/candidates/{cid}/export")
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-disposition"].startswith("attachment;")
        body = resp.json()

        for table, where in es.ERASURE_STEPS:
            held = db_session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), {"cid": cid}
            ).scalar_one()
            section = next(s for s in body["sections"] if s["table"] == table)
            assert held > 0, f"fixture missed {table}"
            assert len(section["rows"]) == held, table

        profile = next(s for s in body["sections"] if s["table"] == "candidates")["rows"][0]
        assert profile["id"] == cid
        assert "embedding" not in profile
        application = next(s for s in body["sections"] if s["table"] == "job_applications")["rows"][0]
        assert "public_token" not in application
        resume = next(s for s in body["sections"] if s["table"] == "resumes")["rows"][0]
        assert "vector_embedding" not in resume and "file_path" not in resume
        assert {(o["table"], o["column"]) for o in body["omitted"]} >= {
            ("job_applications", "public_token"),
            ("resumes", "vector_embedding"),
        }
        assert SECRET_TOKEN not in resp.text
        assert bystander not in resp.text and bystander_email not in resp.text

        assert body["references"]["jobs"][str(job.id)] == "Data Export Test Engineer"
        assert body["references"]["staff"][staff_users["interviewer"].id] == staff_users["interviewer"].name
        assert body["references"]["stages"], "stage history names its stages"

        # The download is an audited export, and shows up in the next one.
        event = (
            db_session.query(AuditEvent)
            .filter(AuditEvent.candidate_id == cid, AuditEvent.action == "export")
            .order_by(AuditEvent.id.desc())
            .first()
        )
        assert event is not None
        assert event.endpoint == "GET /api/candidates/{candidate_id}/export"
        assert event.status_code == 200

        text_resp = admin_client.get(f"/api/candidates/{cid}/export.txt")
        assert text_resp.status_code == 200, text_resp.text
        assert text_resp.headers["content-type"].startswith("text/plain")
        assert text_resp.headers["content-disposition"].endswith('.txt"')
        document = text_resp.text
        assert document.startswith("Data held about Erasure target")
        for expected in (
            "Phone screen went well.",
            "Strong systems answers.",
            "Data Export Test Engineer",
            staff_users["interviewer"].name,
            "INTERVIEW FEEDBACK",
            "WHO HAS ACCESSED THIS RECORD",
            "/api/candidates/{candidate_id}/export",
        ):
            assert expected in document, expected
        assert SECRET_TOKEN not in document
        assert bystander_email not in document
        assert "—" not in document

        history = admin_client.get(f"/api/candidates/{cid}/export").json()["access_history"]
        assert any(e["action"] == "export" for e in history)
        assert all("actor_id" not in e for e in history)
    finally:
        _cleanup(db_session, storage, [cid, bystander], job)


def test_export_is_admin_only(
    db_session, hiring_manager_client, hiring_team_client, interviewer_client, demo_client
):
    cid = db_session.execute(text("SELECT id FROM candidates ORDER BY id LIMIT 1")).scalar_one()
    for client in (hiring_manager_client, hiring_team_client, interviewer_client, demo_client):
        for path in (f"/api/candidates/{cid}/export", f"/api/candidates/{cid}/export.txt"):
            resp = client.get(path)
            assert resp.status_code == 403, (path, resp.status_code, resp.text)


def test_export_of_unknown_candidate_is_404(admin_client):
    missing = "00000000-0000-4000-8000-00000000e404"
    assert admin_client.get(f"/api/candidates/{missing}/export").status_code == 404
    assert admin_client.get(f"/api/candidates/{missing}/export.txt").status_code == 404


def test_audit_classifies_both_export_routes_as_exports():
    from backend.services import audit_service

    for template in ("/api/candidates/{candidate_id}/export", "/api/candidates/{candidate_id}/export.txt"):
        rule = audit_service.rule_for("GET", template)
        assert rule is not None and rule.action == "export", template
        assert rule.id_param == "candidate_id"
