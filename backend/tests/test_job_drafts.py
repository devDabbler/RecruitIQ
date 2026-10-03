"""AI job description drafts (ATS Phase E)."""
from __future__ import annotations

import asyncio

from backend.models.job_draft import JobDraftRequest
from backend.services import job_description_draft as drafting
from backend.services.llm.base import AllProvidersFailedError
from backend.tests.phase_e_helpers import staff_client


class FakeLLM:
    def __init__(self, data=None, error=None):
        self.data = data or {
            "job_overview": "Own the platform — end to end.",
            "required_qualifications": "Python\nSQL",
        }
        self.error = error
        self.calls = []

    async def generate_structured(self, prompt, schema, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error:
            raise self.error
        return self.data


REQUEST = {
    "title": "Platform Engineer, contact me at hm@example.test or 555-123-4567",
    "department": "Engineering",
    "experience_level": "senior",
    "location_type": "remote",
    "skills": ["Python", "Kubernetes"],
}


def test_prompt_holds_only_job_fields_and_is_scrubbed():
    prompt = drafting.build_prompt(JobDraftRequest(**REQUEST))
    assert "Platform Engineer" in prompt and "Kubernetes" in prompt and "senior" in prompt
    assert "hm@example.test" not in prompt and "555-123-4567" not in prompt


def test_draft_goes_through_the_chain_and_normalizes_dashes():
    llm = FakeLLM()
    draft = asyncio.run(drafting.draft(JobDraftRequest(**REQUEST), llm=llm))
    assert "—" not in draft.job_overview
    assert draft.required_qualifications == "Python\nSQL"
    assert llm.calls[0][1]["task_type"] == "job_description"


def test_draft_route_permissions(demo_client, db_session, override_get_db, monkeypatch):
    monkeypatch.setattr(drafting, "get_llm_service", lambda: FakeLLM())
    url = "/api/job-drafts/description"
    assert demo_client.post(url, json=REQUEST).status_code == 403
    assert staff_client(db_session, "hiring_team").post(url, json=REQUEST).status_code == 403
    response = staff_client(db_session, "hiring_manager").post(url, json=REQUEST)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"job_overview", "required_qualifications"}


def test_draft_route_reports_provider_failure_as_503(admin_client, monkeypatch):
    monkeypatch.setattr(
        drafting, "get_llm_service", lambda: FakeLLM(error=AllProvidersFailedError([RuntimeError("down")]))
    )
    response = admin_client.post("/api/job-drafts/description", json=REQUEST)
    assert response.status_code == 503
    assert "write the description by hand" in response.json()["detail"]
