"""Fixtures for API-level tests (Phase 3a).

Every test here runs the real FastAPI app against the real Postgres schema, but
inside an outer transaction that is rolled back at the end of the session. Route
handlers call `db.commit()` freely; `join_transaction_mode="create_savepoint"`
turns those into savepoint releases so the outer transaction still owns the
undo. Nothing a test writes survives it.

`TestClient(app)` is constructed *without* entering it as a context manager on
purpose: that skips the startup event (agent framework init, LLM warmup), which
the API contract tests do not need and which would make them slow and
network-dependent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.models import (
    Candidate,
    CandidateSkill,
    Job,
    JobApplication,
    Resume,
    SavedJob,
)
from backend.utils.database import engine, get_db

# Fixed timestamp so seeded rows sort deterministically regardless of when the
# suite runs.
SEED_EPOCH = datetime(2025, 1, 1, 12, 0, 0)

# Distinctive enough that a keyword search for it can only match seeded rows,
# so list endpoints return the same thing on a loaded dev database and an empty
# CI one.
SEED_EMAIL_DOMAIN = "recruitiq-seed.example.com"


@pytest.fixture(scope="session")
def db_connection():
    connection = engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="session")
def db_session(db_connection) -> Session:
    session = Session(bind=db_connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def seed(db_session: Session):
    """Insert a small, fully deterministic dataset and return its identifiers.

    Deliberately small: the point is to give every screen-reachable route a
    non-empty response to capture, not to mirror production volume. The demo
    dataset (spec §7) is a separate, larger artifact.
    """
    candidate_ids = [
        "00000000-0000-4000-8000-00000000000%d" % i for i in range(1, 4)
    ]
    # example.com, not example.test: email-validator rejects the reserved .test
    # TLD, so a .test address cannot round-trip through POST /api/candidates/.
    people = [
        ("Ada", "Lovelace", f"ada@{SEED_EMAIL_DOMAIN}", "Staff Data Engineer", "Analytical Engines"),
        ("Grace", "Hopper", f"grace@{SEED_EMAIL_DOMAIN}", "Principal Engineer", "US Navy"),
        ("Alan", "Turing", f"alan@{SEED_EMAIL_DOMAIN}", "Research Scientist", "NPL"),
    ]

    jobs = [
        Job(
            title="Senior Data Engineer",
            department="Engineering",
            job_overview="Own the analytics pipeline end to end.",
            required_qualifications="Python, SQL, dbt, 5+ years",
            location="Remote",
            location_type="remote",
            job_type="full_time",
            experience_level="senior",
            min_salary=170000,
            max_salary=210000,
            hiring_manager="Jean Bartik",
            recruiter="Sean C.",
            status="open",
            skills="Python,SQL,dbt,Airflow",
            job_metadata={},
            views=0,
            applications=0,
            created_at=SEED_EPOCH,
            updated_at=SEED_EPOCH,
        ),
        Job(
            title="Machine Learning Engineer",
            department="Research",
            job_overview="Ship models to production.",
            required_qualifications="PyTorch, distributed training, 3+ years",
            location="New York, NY",
            location_type="hybrid",
            job_type="full_time",
            experience_level="mid",
            min_salary=150000,
            max_salary=195000,
            hiring_manager="Jean Bartik",
            recruiter="Sean C.",
            status="open",
            skills="Python,PyTorch,Kubernetes",
            job_metadata={},
            views=0,
            applications=0,
            created_at=SEED_EPOCH,
            updated_at=SEED_EPOCH,
        ),
    ]
    db_session.add_all(jobs)
    db_session.flush()

    for offset, (candidate_id, (first, last, email, position, company)) in enumerate(
        zip(candidate_ids, people)
    ):
        created = SEED_EPOCH + timedelta(days=offset)
        db_session.add(
            Candidate(
                id=candidate_id,
                first_name=first,
                last_name=last,
                email=email,
                phone="+1-555-010%d" % offset,
                location="Remote",
                headline=f"{position} with a long track record",
                source="referral",
                status="active",
                position_applied=jobs[0].title,
                job_id=jobs[0].id,
                notes="Seeded by the API contract suite.",
                current_position=position,
                current_company=company,
                created_at=created,
                updated_at=created,
            )
        )
        db_session.flush()
        for skill in ("Python", "SQL"):
            db_session.add(
                CandidateSkill(
                    candidate_id=candidate_id,
                    skill_name=skill,
                    proficiency="advanced",
                    years_of_experience=5,
                    created_at=created,
                    updated_at=created,
                )
            )
        db_session.add(
            Resume(
                candidate_id=candidate_id,
                file_id=f"seed-{candidate_id}",
                file_path=f"resumes/seed-{candidate_id}.pdf",
                file_name=f"{first.lower()}_{last.lower()}.pdf",
                file_type="pdf",
                parsed_content=f"{first} {last}\n{position} at {company}\nPython, SQL",
                parsed_data={
                    "personal_info": {
                        "name": f"{first} {last}",
                        "email": email,
                        "location": "Remote",
                    },
                    "summary": f"{position} with a long track record",
                    "experience": [
                        {
                            "title": position,
                            "company": company,
                            "start_date": "2019-01-01",
                            "end_date": "Present",
                            "description": "Built things.\nShipped things.",
                        }
                    ],
                    "education": [],
                    "skills": ["Python", "SQL"],
                },
                validation_status="valid",
                validation_score=0.95,
                created_at=created,
                updated_at=created,
            )
        )

    db_session.flush()

    application = JobApplication(
        job_id=jobs[0].id,
        candidate_id=candidate_ids[0],
        status="reviewing",
        cover_letter="I would like to be considered.",
        applied_at=SEED_EPOCH,
        updated_at=SEED_EPOCH,
        source="direct",
    )
    saved_job = SavedJob(
        job_id=jobs[1].id,
        candidate_id=candidate_ids[0],
        saved_at=SEED_EPOCH,
        notes="Interesting team.",
    )
    db_session.add_all([application, saved_job])
    db_session.flush()

    resume_id = (
        db_session.query(Resume.id)
        .filter(Resume.candidate_id == candidate_ids[0])
        .scalar()
    )

    return {
        "candidate_ids": candidate_ids,
        "candidate_id": candidate_ids[0],
        "job_ids": [job.id for job in jobs],
        "job_id": jobs[0].id,
        "resume_id": resume_id,
        "application_id": application.id,
    }


@pytest.fixture(scope="session")
def client(db_session: Session, seed):
    app.dependency_overrides[get_db] = lambda: db_session
    # A handler that blows up should be *recorded* as a 500, not raised out of
    # the capture fixture — a contract suite that dies on the first broken route
    # tells you nothing about the other twenty.
    test_client = TestClient(app, raise_server_exceptions=False)
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:8]}@{SEED_EMAIL_DOMAIN}"
