import os
from pathlib import Path
import json
import time

import pytest


@pytest.mark.integration
@pytest.mark.slow
def test_resume_upload_and_analysis_via_assistant_agent_uses_nebius(monkeypatch):
    """
    End-to-end integration test (no mocks) for the resume upload → analysis workflow
    through the assistant agent endpoint. This test:
      - Forces Nebius on and OpenRouter off via environment variables
      - Uploads a real PDF resume to /api/assistant/agent-task for ResumeProcessingAgent
      - Asserts parsed data and analysis artifacts (hiring_recommendation, etc.) are returned

    Notes:
      - Requires a valid NEBIUS_API_KEY in environment (or .env loaded by the app)
      - Requires outbound network connectivity to Nebius
    """
    # Ensure we have a Nebius key, otherwise skip this live-test gracefully
    nebius_key = os.getenv("NEBIUS_API_KEY", "") or os.getenv("NEBIUS_API_TOKEN", "")
    if not nebius_key:
        pytest.skip("NEBIUS_API_KEY not set; skipping live Nebius integration test")

    # Force routing: Nebius enabled, OpenRouter disabled for this test run
    monkeypatch.setenv("NEBIUS_ENABLED", "true")
    monkeypatch.setenv("OPENROUTER_ENABLED", "false")
    # Use a known-valid Nebius model unless overridden by .env
    monkeypatch.setenv("NEBIUS_MODEL", os.getenv("NEBIUS_MODEL", "microsoft/phi-3-mini-4k-instruct"))

    # Import the FastAPI app after env is configured
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # Prepare upload payload as the UI does
    agent_name = "ResumeProcessingAgent"
    task_details = {
        "target_job_title": "Data Engineer",
        # Session id optional; included to mimic real UI calls
        "session_id": "test-session-nebius-e2e"
    }

    # Use the sample resume in repo root
    root = Path(__file__).resolve().parents[1]
    resume_path = root / "April Drake Test Resume.pdf"
    assert resume_path.exists(), f"Sample resume not found: {resume_path}"

    files = [
        (
            "files",
            (
                resume_path.name,
                open(resume_path, "rb"),
                "application/pdf",
            ),
        )
    ]

    data = {
        "agent_name": agent_name,
        "task_details_json": json.dumps(task_details),
    }

    # Execute the agent task synchronously (as router currently returns result inline)
    resp = client.post("/api/assistant/agent-task", data=data, files=files)
    assert resp.status_code == 200, f"Agent task HTTP {resp.status_code}: {resp.text}"

    payload = resp.json()

    # Core assertions: parser output present (accept either 'parsed_data' or 'data')
    assert isinstance(payload, dict)
    parsed = payload.get("parsed_data") or payload.get("data") or {}
    assert isinstance(parsed, dict) and parsed, f"No parsed resume found; keys: {list(payload.keys())}"
    assert isinstance(parsed, dict)
    # Minimal expected fields extracted by structured parser
    assert "personal_info" in parsed
    assert "experience" in parsed
    assert "education" in parsed

    # Analysis artifacts that drive the assistant UI
    assert "hiring_recommendation" in payload
    assert "quality_assessment" in payload
    # Market alignment may depend on graph/LLM paths; assert key exists but allow None
    assert "market_alignment" in payload
    assert "skill_suggestions" in payload
    assert "job_fit_score" in payload

    # Sanity: job fit score within expected range (0..10)
    jfs = payload.get("job_fit_score")
    assert isinstance(jfs, (int, float)) and 0.0 <= float(jfs) <= 10.0

    # Optional: quick trace that Nebius path is configured (cannot assert from payload)
    # But at least verify our env flags took effect for this process
    assert os.getenv("NEBIUS_ENABLED", "").lower() == "true"
    assert os.getenv("OPENROUTER_ENABLED", "").lower() == "false"


