"""Complete candidate erasure (pilot plan Track 1 #2).

Deleting a candidate has to leave nothing behind: no rows in any table that
leads back to them, no stored resume file, no cached parse. These tests build
a candidate with a row in every one of those tables, delete them through the
API, and count what is left.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from backend.main import app
from backend.models.models import Job, JobApplication
from backend.services import erasure_service as es
from backend.services import pipeline_service as ps
from backend.services.service_registry import provide_resume_service
from backend.services.storage_service import StorageService
from backend.tests.conftest import SEED_EMAIL_DOMAIN, SEED_EPOCH


def _tables_referencing_candidates(db_session) -> set[str]:
    """Every table whose rows hang off a candidate, directly or through a parent."""
    edges = db_session.execute(
        text(
            "SELECT conrelid::regclass::text AS child, confrelid::regclass::text AS parent "
            "FROM pg_constraint WHERE contype = 'f'"
        )
    ).all()
    found = {"candidates"}
    grew = True
    while grew:
        grew = False
        for child, parent in edges:
            if parent in found and child not in found:
                found.add(child)
                grew = True
    return found


def test_erasure_covers_every_table_that_references_candidates(db_session):
    """A new table holding candidate data must be added to ERASURE_STEPS.

    Fails in both directions: a table the erasure misses, and a stale entry
    for a table that no longer leads back to candidates.
    """
    assert _tables_referencing_candidates(db_session) == es.ERASED_TABLES


@pytest.fixture
def storage(tmp_path):
    store = StorageService(storage_dir=str(tmp_path))
    app.dependency_overrides[provide_resume_service] = lambda: SimpleNamespace(storage_service=store)
    try:
        yield store
    finally:
        app.dependency_overrides.pop(provide_resume_service, None)


def _job(db_session, title: str) -> Job:
    job = Job(
        title=title,
        department="Engineering",
        job_overview="Exists for erasure tests.",
        required_qualifications="Python",
        location="Remote",
        location_type="remote",
        job_type="full_time",
        experience_level="mid",
        status="open",
        skills="Python",
        job_metadata={},
        views=0,
        applications=0,
        created_at=SEED_EPOCH,
        updated_at=SEED_EPOCH,
    )
    db_session.add(job)
    db_session.flush()
    return job


def _candidate(db_session, label: str) -> str:
    candidate_id = str(uuid.uuid4())
    db_session.execute(
        text(
            "INSERT INTO candidates (id, first_name, last_name, email, status, created_at, updated_at) "
            "VALUES (:id, 'Erasure', :label, :email, 'active', :ts, :ts)"
        ),
        {
            "id": candidate_id,
            "label": label,
            "email": f"erasure-{label}-{candidate_id[:8]}@{SEED_EMAIL_DOMAIN}",
            "ts": SEED_EPOCH,
        },
    )
    return candidate_id


def _apply(db_session, job: Job, candidate_id: str) -> JobApplication:
    application = JobApplication(
        job_id=job.id,
        candidate_id=candidate_id,
        status="active",
        applied_at=SEED_EPOCH,
        updated_at=SEED_EPOCH,
        source="direct",
    )
    db_session.add(application)
    db_session.flush()
    ps.start_application(db_session, application)
    job.applications = (job.applications or 0) + 1
    db_session.flush()
    return application


def _full_candidate(db_session, storage, staff_users, job: Job) -> dict:
    """A candidate with at least one row in every table ERASED_TABLES names."""
    cid = _candidate(db_session, "target")
    application = _apply(db_session, job, cid)
    params = {"cid": cid, "app": application.id, "job": job.id, "ts": SEED_EPOCH}

    upload = os.path.join(storage.storage_dir, "upload.txt")
    with open(upload, "w", encoding="utf-8") as fh:
        fh.write("Synthetic resume for an erasure test.")
    file_id = asyncio.run(
        storage.store_document(file_path=upload, file_name="resume.txt", content_type="text/plain")
    )

    stage_row = db_session.execute(
        text("SELECT id FROM application_stages WHERE application_id = :app ORDER BY id LIMIT 1"),
        params,
    ).scalar_one()
    interview_id = db_session.execute(
        text(
            "INSERT INTO interviews (application_stage_id, interviewer_id, assignment_source) "
            "VALUES (:row, :who, 'manual') RETURNING id"
        ),
        {"row": stage_row, "who": staff_users["interviewer"].id},
    ).scalar_one()
    statements = [
        (
            "INSERT INTO feedback (interview_id, rating, recommendation, notes) "
            "VALUES (:iid, 4, 'yes', 'Strong systems answers.')"
        ),
        (
            "INSERT INTO email_log (application_id, to_address, subject, body, status) "
            "VALUES (:app, 'erasure@" + SEED_EMAIL_DOMAIN + "', 'Update', 'Hello', 'sent')"
        ),
        "INSERT INTO notes (candidate_id, application_id, body) VALUES (:cid, :app, 'Phone screen went well.')",
        "INSERT INTO candidate_tags (candidate_id, tag) VALUES (:cid, 'erasure-test')",
        "INSERT INTO candidate_skills (candidate_id, skill_name) VALUES (:cid, 'Python')",
        "INSERT INTO candidate_education (candidate_id) VALUES (:cid)",
        "INSERT INTO candidate_experience (candidate_id) VALUES (:cid)",
        "INSERT INTO saved_jobs (job_id, candidate_id) VALUES (:job, :cid)",
        (
            "INSERT INTO candidate_pitches (id, candidate_id, job_id, title, content) "
            "VALUES (:pid, :cid, :job, 'Pitch', 'Synthetic pitch.')"
        ),
        (
            "INSERT INTO resumes (candidate_id, file_id, file_name, parsed_content, parsed_data) "
            "VALUES (:cid, :fid, 'resume.txt', 'Synthetic resume text.', "
            "CAST(:pd AS json))"
        ),
    ]
    extra = {
        "iid": interview_id,
        "pid": str(uuid.uuid4()),
        "fid": file_id,
        "pd": '{"content_hash": "erasure-test-hash"}',
    }
    for sql in statements:
        db_session.execute(text(sql), {**params, **extra})
    db_session.commit()
    return {"candidate_id": cid, "application_id": application.id, "file_id": file_id}


def _leftovers(db_session, cid: str, application_id: int) -> dict[str, int]:
    counts = {}
    for table, where in es.ERASURE_STEPS:
        counts[table] = db_session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), {"cid": cid}
        ).scalar_one()
    # Rows reached only through the application id, in case a step's subquery
    # stopped matching once the application row was gone.
    for table in ("application_stages", "email_log"):
        counts[f"{table}_by_app"] = db_session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE application_id = :app"), {"app": application_id}
        ).scalar_one()
    return counts


def test_delete_removes_every_trace(db_session, admin_client, staff_users, storage):
    job = _job(db_session, "Erasure Test Engineer")
    target = _full_candidate(db_session, storage, staff_users, job)
    # A second candidate on the same job must come through untouched.
    bystander = _candidate(db_session, "bystander")
    bystander_app = _apply(db_session, job, bystander)
    db_session.commit()

    before = _leftovers(db_session, target["candidate_id"], target["application_id"])
    assert all(before.values()), f"fixture missed a table: {before}"
    assert storage_has(storage, target["file_id"])

    resp = admin_client.delete(f"/api/candidates/{target['candidate_id']}")
    assert resp.status_code == 200, resp.text

    after = _leftovers(db_session, target["candidate_id"], target["application_id"])
    assert not any(after.values()), f"left behind: { {k: v for k, v in after.items() if v} }"
    assert not storage_has(storage, target["file_id"])

    db_session.expire_all()
    assert db_session.get(JobApplication, bystander_app.id) is not None
    assert db_session.get(Job, job.id).applications == 1

    assert admin_client.delete(f"/api/candidates/{target['candidate_id']}").status_code == 404

    db_session.execute(text("DELETE FROM application_stages WHERE application_id = :a"), {"a": bystander_app.id})
    db_session.execute(text("DELETE FROM job_applications WHERE id = :a"), {"a": bystander_app.id})
    db_session.execute(text("DELETE FROM candidates WHERE id = :c"), {"c": bystander})
    db_session.execute(text("DELETE FROM pipeline_stages WHERE job_id = :j"), {"j": job.id})
    db_session.execute(text("DELETE FROM jobs WHERE id = :j"), {"j": job.id})
    db_session.commit()


def storage_has(storage: StorageService, file_id: str) -> bool:
    return os.path.isdir(os.path.join(storage.storage_dir, file_id))


def test_failed_erasure_removes_nothing(db_session, admin_client, staff_users, storage, monkeypatch):
    job = _job(db_session, "Erasure Rollback Engineer")
    target = _full_candidate(db_session, storage, staff_users, job)
    before = _leftovers(db_session, target["candidate_id"], target["application_id"])

    # Fail on the last step, after every child table has been deleted.
    broken = es.ERASURE_STEPS[:-1] + (("candidates", "no_such_column = :cid"),)
    monkeypatch.setattr(es, "ERASURE_STEPS", broken)
    resp = admin_client.delete(f"/api/candidates/{target['candidate_id']}")
    assert resp.status_code == 500
    monkeypatch.undo()

    db_session.expire_all()
    assert _leftovers(db_session, target["candidate_id"], target["application_id"]) == before
    assert storage_has(storage, target["file_id"]), "file removed although the rows survived"
    assert db_session.get(Job, job.id).applications == 1

    assert admin_client.delete(f"/api/candidates/{target['candidate_id']}").status_code == 200
    db_session.execute(text("DELETE FROM pipeline_stages WHERE job_id = :j"), {"j": job.id})
    db_session.execute(text("DELETE FROM jobs WHERE id = :j"), {"j": job.id})
    db_session.commit()


def test_unknown_candidate_is_404(admin_client, storage):
    assert admin_client.delete(f"/api/candidates/{uuid.uuid4()}").status_code == 404


def test_delete_needs_write_access(client, demo_client, storage, db_session):
    cid = _candidate(db_session, "guarded")
    db_session.commit()
    assert client.delete(f"/api/candidates/{cid}").status_code in (401, 403)
    assert demo_client.delete(f"/api/candidates/{cid}").status_code in (401, 403)
    assert db_session.execute(text("SELECT 1 FROM candidates WHERE id = :c"), {"c": cid}).first()
    db_session.execute(text("DELETE FROM candidates WHERE id = :c"), {"c": cid})
    db_session.commit()


class _FakeRedis:
    def __init__(self, keys):
        self.keys = set(keys)

    def scan_iter(self, match):
        prefix = match.rstrip("*")
        return [k for k in self.keys if k.startswith(prefix)]

    def delete(self, *keys):
        hit = self.keys & set(keys)
        self.keys -= hit
        return len(hit)


def test_parse_and_duplicate_cache_entries_are_cleared(db_session):
    from backend.utils.cache_utils import make_cache_key

    cid = _candidate(db_session, "cached")
    db_session.execute(
        text(
            "INSERT INTO resumes (candidate_id, parsed_data) "
            "VALUES (:cid, CAST('{\"content_hash\": \"abc123\"}' AS json))"
        ),
        {"cid": cid},
    )
    db_session.commit()
    unrelated = make_cache_key("resume_parse", "zzz999")
    fake = _FakeRedis(
        [make_cache_key("resume_parse", "abc123"), "duplicate:abc123:2048", "duplicate:zzz999:10", unrelated]
    )

    report = es.erase_candidate(db_session, cid, storage=None, redis_client=fake)

    assert report.cache_keys_removed == 2
    assert fake.keys == {"duplicate:zzz999:10", unrelated}


def test_storage_refuses_a_path_as_file_id(tmp_path):
    store = StorageService(storage_dir=str(tmp_path / "store"))
    (tmp_path / "keep").mkdir()
    with pytest.raises(ValueError):
        store.delete_document("../keep")
    assert (tmp_path / "keep").is_dir()
    assert store.delete_document(str(uuid.uuid4())) is False
