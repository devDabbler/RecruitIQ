"""Shared setup for the ATS Phase C tests.

`client_for_role` builds a signed-in TestClient for a brand-new user of any
role. Phase B's session-wide `interviewer_client` exists too, but other modules
assign interviews to that user, and the Phase C visibility tests need an
interviewer who is assigned to nobody. It commits the user rather than
flushing: a route that errors rolls the shared session back to its last
commit, and a merely flushed user would vanish mid-module. Callers must depend
on the `override_get_db` fixture (directly or through `client`, `admin_client`,
or `demo_client`) so the app reads the test session.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.models import User
from backend.utils.auth import create_access_token

from .conftest import SEED_EMAIL_DOMAIN, SEED_EPOCH

JOB_PAYLOAD = {
    "department": "Engineering",
    "job_overview": "Exists for the Phase C tests.",
    "required_qualifications": "Python",
    "skills": ["Python"],
}


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def client_for_role(db_session: Session, role: str) -> TestClient:
    user = User(
        email=f"{unique(role)}@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role=role,
        name=f"Test {role.replace('_', ' ').title()}",
        created_at=SEED_EPOCH,
    )
    db_session.add(user)
    db_session.commit()
    return TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Authorization": f"Bearer {create_access_token(user)}"},
    )


def new_candidate(admin_client: TestClient, job_id: Optional[int] = None, **extra) -> str:
    """Create a candidate through the API and return its id."""
    payload = {
        "first_name": "Intake",
        "last_name": "Test",
        "email": f"{unique('intake')}@{SEED_EMAIL_DOMAIN}",
        **extra,
    }
    if job_id is not None:
        payload["job_id"] = job_id
    response = admin_client.post("/api/candidates/", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def new_job(admin_client: TestClient, title_prefix: str = "Phase C Job") -> int:
    response = admin_client.post(
        "/api/jobs/", json={**JOB_PAYLOAD, "title": f"{title_prefix} {unique('j')}"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def application_id_for(client: TestClient, candidate_id: str, job_id: int) -> int:
    rows = client.get(f"/api/jobs/applications/{candidate_id}").json()
    return next(row["id"] for row in rows if row["job_id"] == job_id)


def job_with_applicants(admin_client: TestClient, count: int) -> tuple[int, list[str], list[int]]:
    """A fresh job with `count` new candidates at Resume submitted."""
    job_id = new_job(admin_client, "Bulk Test")
    candidate_ids = [new_candidate(admin_client, job_id=job_id) for _ in range(count)]
    application_ids = [application_id_for(admin_client, cid, job_id) for cid in candidate_ids]
    return job_id, candidate_ids, application_ids
