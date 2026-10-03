"""Helpers shared by the Phase E test files.

`make_application` builds its own job, candidate, and application so a test
never depends on (or disturbs) the session-wide seed, and it commits: a route
that answers 409 rolls the shared session back to its last commit, which
would otherwise delete rows a test had only flushed.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from backend.main import app
from backend.models.models import Candidate, Job, JobApplication, User
from backend.services import pipeline_service as ps
from backend.utils.auth import create_access_token

SEED_EMAIL_DOMAIN = "recruitiq-seed.example.com"
APPLIED_AT = datetime(2025, 1, 1, 12, 0, 0)


def make_application(
    db_session,
    *,
    job: Job | None = None,
    first_name: str = "Mira",
    last_name: str = "Quillfeather",
    hiring_manager: str = "Hollis Brandt",
    recruiter: str = "Ines Marlow",
) -> tuple[Job, JobApplication]:
    """A fresh candidate applied to `job` (a new job when None), started at stage 1."""
    if job is None:
        job = Job(
            title="Platform Engineer",
            department="Engineering",
            job_overview="Build the platform.",
            required_qualifications="Python, 4+ years",
            location="Remote",
            location_type="remote",
            job_type="full_time",
            experience_level="mid",
            hiring_manager=hiring_manager,
            recruiter=recruiter,
            status="open",
            skills="Python,SQL",
            job_metadata={},
            views=0,
            applications=0,
        )
        db_session.add(job)
        db_session.flush()

    candidate_id = str(uuid.uuid4())
    db_session.add(
        Candidate(
            id=candidate_id,
            first_name=first_name,
            last_name=last_name,
            email=f"{first_name.lower()}-{candidate_id[:8]}@{SEED_EMAIL_DOMAIN}",
            phone="+1-555-0199",
            status="active",
            source="referral",
            notes="Internal: expects a counter offer.",
        )
    )
    db_session.flush()

    application = JobApplication(
        job_id=job.id,
        candidate_id=candidate_id,
        applied_at=APPLIED_AT,
        updated_at=APPLIED_AT,
        source="referral",
    )
    db_session.add(application)
    db_session.flush()
    ps.start_application(db_session, application)
    db_session.commit()
    return job, application


def staff_user(db_session, role: str, name: str | None = None) -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role=role,
        name=name or f"Test {role.replace('_', ' ').title()}",
    )
    db_session.add(user)
    db_session.commit()
    return user


def staff_client(db_session, role: str) -> TestClient:
    """A client signed in as a fresh user with `role`. Needs `override_get_db`."""
    token = create_access_token(staff_user(db_session, role))
    return TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Authorization": f"Bearer {token}"},
    )


def keys_by_status(application: JobApplication, status: str) -> list[str]:
    rows = sorted(application.stages, key=lambda r: r.stage.position)
    return [r.stage.key for r in rows if r.status == status]
