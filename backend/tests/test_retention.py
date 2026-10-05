"""Candidate retention (pilot plan Track 1 #6).

The job erases candidates nobody has worked on within the window, holds back
anyone with a process still running, and records each erasure in the audit
log. Fixture candidates are dated in 2001 and the job is run with `now` in
early 2002, so nothing else in the database falls inside the window.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from backend.models.models import Job, JobApplication
from backend.services import erasure_service as es
from backend.services import retention_service as rs
from backend.tests.conftest import SEED_EMAIL_DOMAIN, SEED_EPOCH

OLD = datetime(2001, 1, 1, 9, 0, 0)
RECENT = datetime(2001, 12, 20, 9, 0, 0)
NOW = datetime(2002, 1, 1, 9, 0, 0)
DAYS = 30  # cutoff 2001-12-02: OLD is past it, RECENT is inside it

# erase_candidate clears Redis cache keys; nothing here should touch a real one.
NO_REDIS = SimpleNamespace(scan_iter=lambda match: iter(()), delete=lambda *keys: 0)


def test_activity_columns_cover_every_erased_table():
    """A new candidate table needs a decision about what counts as activity."""
    assert set(rs.ACTIVITY_COLUMNS) == es.ERASED_TABLES


def test_activity_columns_exist(db_session):
    for table, columns in rs.ACTIVITY_COLUMNS.items():
        for column in columns:
            found = db_session.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ),
                {"t": table, "c": column},
            ).first()
            assert found, f"{table}.{column} does not exist"


@pytest.mark.parametrize("days", [0, 1, 29, -5])
def test_short_windows_are_refused(db_session, days):
    with pytest.raises(rs.RetentionConfigError):
        rs.run_retention(db_session, days, dry_run=True, now=NOW)


def _job(db_session) -> Job:
    job = Job(
        title="Retention Test Engineer",
        department="Engineering",
        job_overview="Exists for retention tests.",
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


def _candidate(db_session, label: str, when) -> str:
    candidate_id = str(uuid.uuid4())
    db_session.execute(
        text(
            "INSERT INTO candidates (id, first_name, last_name, email, status, created_at, updated_at) "
            "VALUES (:id, 'Retention', :label, :email, 'active', :ts, :ts)"
        ),
        {
            "id": candidate_id,
            "label": label,
            "email": f"retention-{label}-{candidate_id[:8]}@{SEED_EMAIL_DOMAIN}",
            "ts": when,
        },
    )
    return candidate_id


def _apply(db_session, job: Job, candidate_id: str, status: str) -> JobApplication:
    application = JobApplication(
        job_id=job.id,
        candidate_id=candidate_id,
        status=status,
        applied_at=OLD,
        updated_at=OLD,
        source="direct",
    )
    db_session.add(application)
    db_session.flush()
    return application


@pytest.fixture
def people(db_session):
    job = _job(db_session)
    ids = {
        # Rejected long ago, nothing since: erased.
        "stale": _candidate(db_session, "stale", OLD),
        # No application at all, profile untouched since 2001: erased.
        "dormant": _candidate(db_session, "dormant", OLD),
        # Old profile, but a recruiter left a note recently: kept.
        "noted": _candidate(db_session, "noted", OLD),
        # Old and quiet, but the application is still in progress: held.
        "open": _candidate(db_session, "open", OLD),
        # Recent profile: not even considered.
        "fresh": _candidate(db_session, "fresh", RECENT),
    }
    _apply(db_session, job, ids["stale"], "rejected")
    _apply(db_session, job, ids["open"], "active")
    db_session.execute(
        text("INSERT INTO notes (candidate_id, body, created_at) VALUES (:cid, 'Still interested.', :ts)"),
        {"cid": ids["noted"], "ts": RECENT},
    )
    db_session.commit()
    yield ids

    for cid in ids.values():
        if db_session.execute(text("SELECT 1 FROM candidates WHERE id = :c"), {"c": cid}).first():
            es.erase_candidate(db_session, cid, redis_client=NO_REDIS)
    db_session.execute(text("DELETE FROM pipeline_stages WHERE job_id = :j"), {"j": job.id})
    db_session.execute(text("DELETE FROM jobs WHERE id = :j"), {"j": job.id})
    db_session.commit()


def _exists(db_session, cid: str) -> bool:
    return db_session.execute(text("SELECT 1 FROM candidates WHERE id = :c"), {"c": cid}).first() is not None


def _ours(candidates, ids) -> dict[str, rs.InactiveCandidate]:
    by_id = {c.candidate_id: c for c in candidates}
    return {label: by_id[cid] for label, cid in ids.items() if cid in by_id}


def test_dry_run_reports_and_changes_nothing(db_session, people):
    report = rs.run_retention(db_session, DAYS, dry_run=True, now=NOW, redis_client=NO_REDIS)

    assert set(_ours(report.expired, people)) == {"stale", "dormant"}
    held = _ours(report.held, people)
    assert set(held) == {"open"}
    assert held["open"].held == rs.HELD_OPEN_APPLICATION
    assert report.erased == []
    assert all(_exists(db_session, cid) for cid in people.values())
    assert "would erase" in report.summary()


def test_run_erases_inactive_and_audits_it(db_session, people):
    report = rs.run_retention(db_session, DAYS, now=NOW, redis_client=NO_REDIS)

    assert {people["stale"], people["dormant"]} <= set(report.erased)
    assert not _exists(db_session, people["stale"])
    assert not _exists(db_session, people["dormant"])
    for label in ("noted", "open", "fresh"):
        assert _exists(db_session, people[label]), f"{label} should have survived"
    # Erasure is the complete one: the stale candidate's application went too.
    assert not db_session.execute(
        text("SELECT 1 FROM job_applications WHERE candidate_id = :c"), {"c": people["stale"]}
    ).first()

    events = db_session.execute(
        text(
            "SELECT actor_id, actor_role, action, subject_type, endpoint, detail FROM audit_events "
            "WHERE candidate_id = :c"
        ),
        {"c": people["stale"]},
    ).all()
    assert [tuple(e) for e in events] == [
        (None, "system", "delete", "candidate", rs.AUDIT_ENDPOINT, f"retention {DAYS}d")
    ]


def test_one_failure_does_not_stop_the_rest(db_session, people, monkeypatch):
    real_erase = es.erase_candidate

    def flaky(db, cid, **kwargs):
        if cid == people["stale"]:
            raise RuntimeError("disk on fire")
        return real_erase(db, cid, **kwargs)

    monkeypatch.setattr(es, "erase_candidate", flaky)
    report = rs.run_retention(db_session, DAYS, now=NOW, redis_client=NO_REDIS)

    assert people["stale"] in report.failed
    assert people["dormant"] in report.erased
    assert _exists(db_session, people["stale"])
    assert not _exists(db_session, people["dormant"])
    assert "failed 1" in report.summary()


def test_undated_candidates_are_held(db_session):
    cid = str(uuid.uuid4())
    db_session.execute(
        text(
            "INSERT INTO candidates (id, first_name, last_name, email, status, created_at, updated_at) "
            "VALUES (:id, 'Retention', 'Undated', :email, 'active', NULL, NULL)"
        ),
        {"id": cid, "email": f"retention-undated-{cid[:8]}@{SEED_EMAIL_DOMAIN}"},
    )
    db_session.commit()
    try:
        expired, held = rs.find_inactive(db_session, NOW)
        assert cid not in {c.candidate_id for c in expired}
        assert _ours(held, {"undated": cid})["undated"].held == rs.HELD_UNDATED
    finally:
        db_session.execute(text("DELETE FROM candidates WHERE id = :c"), {"c": cid})
        db_session.commit()


class _Captured:
    def __init__(self):
        self.calls = []

    def __call__(self, db, days, **kwargs):
        self.calls.append({"days": days, **kwargs})
        return rs.RetentionReport(days=days, cutoff=NOW, dry_run=kwargs["dry_run"])


@pytest.fixture
def script(monkeypatch):
    from scripts import retention as script_module

    captured = _Captured()
    monkeypatch.setattr(script_module.retention_service, "run_retention", captured)
    monkeypatch.setattr(script_module, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(script_module, "resume_storage", lambda: "storage")

    def run(argv, mode="internal", retention_days=365):
        settings = SimpleNamespace(
            retention_days=retention_days, deployment_mode=mode, is_internal=mode == "internal"
        )
        monkeypatch.setattr(script_module, "get_settings", lambda: settings)
        monkeypatch.setattr("sys.argv", ["retention.py", *argv])
        return script_module.main()

    return run, captured


def test_script_is_off_without_a_window(script):
    run, captured = script
    assert run([], retention_days=0) == 0
    assert captured.calls == []


def test_script_refuses_a_short_window(script):
    run, captured = script
    assert run(["--days", "7"]) == 2
    assert captured.calls == []


def test_script_erases_in_internal_mode(script):
    run, captured = script
    assert run([]) == 0
    assert captured.calls == [{"days": 365, "dry_run": False, "storage": "storage"}]


def test_script_never_erases_the_public_demo(script):
    run, captured = script
    assert run([], mode="public") == 0
    assert captured.calls[0]["dry_run"] is True
