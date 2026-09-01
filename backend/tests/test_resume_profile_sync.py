"""Uploaded resumes must produce first-class candidates (DB-integration).

A saved upload has to look like a seeded candidate: profile fields filled,
skills rows written, and an embedding stored so the assistant's semantic
search and the matching pipeline can see the person at all
(search_candidates_by_text filters on `embedding IS NOT NULL`).
"""
import os
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

POSTGRES_CONN = os.getenv("POSTGRES_CONN", "").strip('"')


def _db_available():
    if not POSTGRES_CONN:
        return False
    try:
        engine = create_engine(POSTGRES_CONN)
        with engine.connect() as conn:
            return conn.execute(text("SELECT count(*) FROM candidates")).scalar() is not None
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="needs Postgres with app schema")


class StubEmbedder:
    def embed_query(self, txt):
        vec = [0.0] * 768
        vec[0] = 1.0
        return vec


class FailingEmbedder:
    def embed_query(self, txt):
        raise ConnectionError("ollama unreachable")


@pytest.fixture
def db():
    engine = create_engine(POSTGRES_CONN)
    session = sessionmaker(bind=engine)()
    yield session
    session.rollback()
    session.close()


def _service(embedder):
    from backend.services.resume_service import ResumeService

    llm = MagicMock()
    llm.get_embedding_model.return_value = embedder
    return ResumeService(storage_service=MagicMock(), llm_service=llm)


def _resume_data(email):
    from backend.utils.resume_parsing.models.resume_schema import ResumeData

    return ResumeData.model_validate(
        {
            "personal_info": {
                "name": "Test Uploadee",
                "email": email,
                "phone": "555-000-1111",
                "location": "Hartford, CT",
                "summary": "Actuarial data engineer with a decade in the insurance industry.",
            },
            "experience": [
                {
                    "title": "Senior Data Engineer",
                    "company": "Travelers",
                    "start_date": "2021",
                    "end_date": "Present",
                    "location": "Hartford, CT",
                    "description": "Claims data pipelines.",
                },
                {
                    "title": "Data Engineer",
                    "company": "Aetna",
                    "start_date": "2016",
                    "end_date": "2021",
                    "description": "Warehouse modeling.",
                },
            ],
            "skills": [{"name": "Python"}, {"name": "SQL"}, {"name": "Airflow"}],
            "raw_text": "Test Uploadee. Senior Data Engineer at Travelers.",
        }
    )


def _cleanup(db, email):
    row = db.execute(text("SELECT id FROM candidates WHERE email = :e"), {"e": email}).fetchone()
    if row:
        for table in ("candidate_skills", "candidate_experience", "candidate_education", "resumes"):
            db.execute(text(f"DELETE FROM {table} WHERE candidate_id = :c"), {"c": row[0]})
        db.execute(text("DELETE FROM candidates WHERE id = :c"), {"c": row[0]})
    db.commit()


def test_save_resume_builds_a_first_class_candidate(db):
    email = f"uploadee-{uuid.uuid4().hex[:10]}@example.test"
    service = _service(StubEmbedder())
    try:
        resume_id = service.save_resume(_resume_data(email), db)
        assert resume_id

        cand = db.execute(
            text(
                "SELECT id, current_position, current_company, location, headline, status, "
                "source, embedding IS NOT NULL AS has_vector "
                "FROM candidates WHERE email = :e"
            ),
            {"e": email},
        ).fetchone()
        assert cand is not None
        assert cand.current_position == "Senior Data Engineer"
        assert cand.current_company == "Travelers"
        assert cand.location == "Hartford, CT"
        assert "insurance" in cand.headline
        assert cand.status == "active"
        assert cand.source == "direct_application"
        assert cand.has_vector is True, "uploaded candidates must be semantically searchable"

        skills = {
            r[0]
            for r in db.execute(
                text("SELECT skill_name FROM candidate_skills WHERE candidate_id = :c"),
                {"c": cand.id},
            )
        }
        assert {"Python", "SQL", "Airflow"} <= skills

        # Regression: the old loop `break`ed at the first current position and
        # dropped every older experience entry.
        exp = db.execute(
            text(
                "SELECT company, start_date, end_date FROM candidate_experience "
                "WHERE candidate_id = :c"
            ),
            {"c": cand.id},
        ).fetchall()
        assert len(exp) == 2
        by_company = {r.company: r for r in exp}
        # Regression: dates used to be lost wholesale (the normalizer returns a
        # tuple; the old code called .get() on it and fell back to nothing).
        assert by_company["Travelers"].start_date is not None
        assert by_company["Travelers"].end_date is None, "'Present' means an ongoing role"
        assert by_company["Aetna"].start_date is not None
        assert by_company["Aetna"].end_date is not None
    finally:
        _cleanup(db, email)


def test_save_resume_survives_unreachable_embedder(db):
    """CI runs with Ollama pointed at a dead port on purpose: the save must
    still land, just without a vector (same state as seed --no-embeddings)."""
    email = f"uploadee-{uuid.uuid4().hex[:10]}@example.test"
    service = _service(FailingEmbedder())
    try:
        resume_id = service.save_resume(_resume_data(email), db)
        assert resume_id

        cand = db.execute(
            text("SELECT current_position, embedding IS NULL AS no_vector FROM candidates WHERE email = :e"),
            {"e": email},
        ).fetchone()
        assert cand is not None
        assert cand.current_position == "Senior Data Engineer"
        assert cand.no_vector is True
    finally:
        _cleanup(db, email)
