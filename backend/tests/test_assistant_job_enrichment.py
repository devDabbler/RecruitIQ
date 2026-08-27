import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.models.models import Job
from backend.routers.assistant import provide_intent_processor
from backend.utils.database import get_db


class FakeIntentProcessor:
    """Stub that forces recruiter_outreach_email and echoes received entities into style."""
    def detect_intent(self, message, conversation_context):
        # Force the intent so we bypass LLM and other branches
        return {
            "intent": "recruiter_outreach_email",
            "entities": {"role": "Software Engineer"},
            "context_updates": {},
        }

    async def process_intent(self, intent, entities, message):
        # Echo back a style that proves job_data enrichment happened
        received_title = None
        try:
            received_title = entities.get("job_data", {}).get("title")
        except Exception:
            pass
        style = {
            "tone": entities.get("tone"),
            "creativity": entities.get("creativity"),
            "subject_line_count": entities.get("subject_line_count"),
            "received_job_title": received_title,
        }
        return {
            "intent_processed": True,
            "response_type": "recruiter_outreach_email",
            "email_body": "Test email body",
            "subject_lines": ["Subject A"],
            "style": style,
            "role": entities.get("role"),
        }


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # Create only the Job table to keep the test isolated and SQLite-friendly
    Job.__table__.create(bind=engine)

    # Seed a Job record
    db = TestingSessionLocal()
    job = Job(title="Senior Data Engineer", department="Data", location="Remote")
    db.add(job)
    db.commit()
    db.refresh(job)

    def _get_db():
        try:
            yield db
        finally:
            pass

    return job, _get_db


def test_recruiter_outreach_job_enrichment():
    # Arrange: override dependencies
    job, db_override = setup_in_memory_db()

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[provide_intent_processor] = lambda: FakeIntentProcessor()

    # Disable startup/shutdown events to avoid real DB checks and agent init
    try:
        app.router.on_startup.clear()
        app.router.on_shutdown.clear()
    except Exception:
        pass

    client = TestClient(app)

    # Provide conversation_context with job_id and style settings
    payload = {
        "message": "Please draft a recruiter outreach email",
        "conversation_history": [],
        "conversation_context": {
            "job_id": job.id,
            "recruiter_email_style": {"tone": "friendly", "creativity": "medium", "subject_line_count": 2},
        },
    }

    # Act
    resp = client.post("/api/assistant/chat", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Assert: response contains style echo with the job title, proving enrichment
    assert data.get("response_type") == "recruiter_outreach_email"
    style = data.get("style") or {}
    assert style.get("tone") == "friendly"
    assert style.get("creativity") == "medium"
    assert style.get("subject_line_count") == 2
    # Most important: router fetched job_data from DB using job_id
    assert style.get("received_job_title") == "Senior Data Engineer"

    # Cleanup overrides
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(provide_intent_processor, None)
