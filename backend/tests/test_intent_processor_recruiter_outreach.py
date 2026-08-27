import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend.services.intent_processor import IntentProcessor

@pytest.mark.asyncio
@pytest.mark.parametrize("role, jobs, expected_job_title, expect_match", [
    ("Data Scientist", [
        MagicMock(id=1, title="Data Scientist", department="Data", job_overview="Analyze data", required_qualifications="PhD", location="Remote", location_type="remote", job_type="full-time", experience_level="senior", skills="python,ml"),
        MagicMock(id=2, title="Software Engineer", department="Engineering", job_overview="Develop software", required_qualifications="BS", location="NYC", location_type="onsite", job_type="full-time", experience_level="mid", skills="python,java")
    ], "Data Scientist", True),
    ("Unicorn Wrangler", [
        MagicMock(id=1, title="Data Scientist", department="Data", job_overview="Analyze data", required_qualifications="PhD", location="Remote", location_type="remote", job_type="full-time", experience_level="senior", skills="python,ml")
    ], None, False)
])
async def test_handle_recruiter_outreach_email_job_matching(monkeypatch, role, jobs, expected_job_title, expect_match):
    # Mock job_service
    job_service = MagicMock()
    job_service.get_jobs.return_value = jobs
    job_service.create_embeddings.side_effect = lambda job_data: {"description": [1.0, 0.0] if job_data["title"] == "Data Scientist" else [0.0, 1.0]}
    # Mock LLM embedding
    llm_service = MagicMock()
    llm_service.get_embedding_model.return_value = MagicMock()
    monkeypatch.setattr(job_service, 'llm_service', llm_service)
    # Patch embedding for role
    from backend.utils import cache_utils
    monkeypatch.setattr(cache_utils, "get_embedding_cached", lambda model, text: [1.0, 0.0] if "Data Scientist" in text else [0.0, 1.0])
    # Mock communications_service
    comm_service = AsyncMock()
    comm_service.generate_recruiter_outreach_email.return_value = {"body": "Email body for job", "subject_lines": ["Subject 1"]}
    # Build processor
    processor = IntentProcessor()
    processor.job_service = job_service
    processor.communications_service = comm_service
    processor.db = MagicMock()
    # Test call
    entities = {"role": role}
    result = await processor._handle_recruiter_outreach_email("recruiter_outreach_email", entities, "Message about role")
    if expect_match:
        assert result["intent_processed"] is True
        assert result["job_match"] is not None
        assert result["job_match"]["title"] == expected_job_title
        assert "Email body" in result["email_body"]
    else:
        assert result["intent_processed"] is True
        assert result["job_match"] is None or result["job_match"] == {}
        assert "Email body" in result["email_body"]

@pytest.mark.asyncio
async def test_handle_recruiter_outreach_email_missing_role():
    processor = IntentProcessor()
    result = await processor._handle_recruiter_outreach_email("recruiter_outreach_email", {}, "Message with no role")
    assert result["intent_processed"] is False
    assert "Missing role" in result["error"]
