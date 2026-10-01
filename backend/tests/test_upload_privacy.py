"""De-identification of an uploaded resume before any post-parse model call.

Two layers are pinned here:

* `anonymize_parsed_resume` itself: which fields go, what the scrubber
  rewrites inside the free text, and what it must leave alone (date ranges
  look a lot like phone numbers).
* The pipeline: `_process_single_file` is driven with a resume full of
  contact details, every prompt it sends is captured, and none of them may
  carry the name, the email, the phone, a link, or the file name. The web
  search service is a tripwire: calling it at all fails the test, which is
  what retired the name-based LinkedIn lookup.

The transparency endpoint that publishes this policy is checked against the
same run, so the list of model calls on the page cannot drift from the calls
the pipeline actually makes.
"""
from __future__ import annotations

import json

import pytest

from backend.services.agent_framework.agents.resume_processing_agent import (
    POST_PARSE_MODEL_CALLS,
    ResumeProcessingAgent,
)
from backend.services.resume_privacy import (
    DROPPED_KEYS,
    IDENTIFYING_FIELDS,
    anonymize_parsed_resume,
)

NAME = "Priya Raman"
EMAIL = "priya.raman@example.com"
PHONE = "(415) 555-0142"
LINKEDIN = "https://www.linkedin.com/in/priya-raman"
GITHUB = "github.com/praman"
FILE_NAME = "Priya_Raman_Resume.pdf"

# Every string that identifies the person and must not reach a prompt.
IDENTIFIERS = [NAME, "Priya", "Raman", EMAIL, "415", "555-0142", "linkedin.com/in", "github.com/praman", FILE_NAME]


def parsed_resume() -> dict:
    return {
        "personal_info": {
            "name": NAME,
            "email": EMAIL,
            "phone": PHONE,
            "address": "12 Harbor Street",
            "location": "Oakland, CA",
            "linkedin": LINKEDIN,
            "github": GITHUB,
            "website": "https://praman.dev",
            "summary": f"{NAME} is a data engineer. Reach Priya at {EMAIL} or {PHONE}.",
        },
        "experience": [
            {
                "company": "Northwind Analytics",
                "title": "Senior Data Engineer",
                "start_date": "2019-03",
                "end_date": "2023-08",
                "location": "Oakland, CA",
                "description": f"Priya led the migration of 2019-2023 pipelines to dbt. Contact: {GITHUB}.",
            }
        ],
        "education": [{"degree": "BS Computer Science", "institution": "UC Davis"}],
        "skills": [{"name": "Python"}, {"name": "SQL"}, {"name": "dbt"}],
        "raw_text": f"{NAME}\n{EMAIL}\n{PHONE}\n{LINKEDIN}\nSenior Data Engineer...",
        "file_name": FILE_NAME,
    }


# --- the function -----------------------------------------------------------


def test_identifying_fields_are_removed_and_the_rest_kept():
    safe, report = anonymize_parsed_resume(parsed_resume())

    for field in IDENTIFYING_FIELDS:
        assert field not in safe["personal_info"], field
    for key in DROPPED_KEYS:
        assert key not in safe, key

    # The professional content is untouched.
    assert [s["name"] for s in safe["skills"]] == ["Python", "SQL", "dbt"]
    assert safe["experience"][0]["company"] == "Northwind Analytics"
    assert safe["experience"][0]["title"] == "Senior Data Engineer"
    assert safe["education"][0]["institution"] == "UC Davis"

    # The report says what went, for the upload screen.
    assert set(report["identifying_fields_removed"]) == set(IDENTIFYING_FIELDS)


def test_free_text_is_scrubbed_of_name_email_phone_and_links():
    safe, report = anonymize_parsed_resume(parsed_resume())

    blob = json.dumps(safe)
    for needle in ("Priya", "Raman", EMAIL, "555-0142", "linkedin.com", "github.com"):
        assert needle not in blob, needle

    summary = safe["personal_info"]["summary"]
    assert summary.startswith("the candidate is a data engineer")
    assert "[email removed]" in summary
    assert "[phone removed]" in summary
    assert "[link removed]" in safe["experience"][0]["description"]

    assert report["name_mentions_scrubbed"] >= 3
    assert report["emails_scrubbed"] == 1
    assert report["phones_scrubbed"] == 1
    assert report["links_scrubbed"] == 1


def test_date_ranges_survive_the_phone_scrubber():
    """"2019-2023" has eight digits and a dash; it is a tenure, not a number."""
    safe, _ = anonymize_parsed_resume(parsed_resume())
    assert "2019-2023" in safe["experience"][0]["description"]
    assert safe["experience"][0]["start_date"] == "2019-03"


def test_the_original_parse_is_not_mutated():
    """The recruiter still gets the full parse; only the models go without."""
    original = parsed_resume()
    anonymize_parsed_resume(original)
    assert original["personal_info"]["name"] == NAME
    assert original["personal_info"]["email"] == EMAIL
    assert "Priya led" in original["experience"][0]["description"]
    assert original["file_name"] == FILE_NAME


def test_a_parse_with_no_personal_info_is_harmless():
    safe, report = anonymize_parsed_resume({"skills": [{"name": "Go"}]})
    assert safe["skills"] == [{"name": "Go"}]
    assert safe["personal_info"] == {}
    assert report["identifying_fields_removed"] == []


# --- the pipeline -----------------------------------------------------------


class CapturingLLM:
    """Records every prompt and system message the agent sends."""

    def __init__(self):
        self.prompts: list[str] = []

    async def generate_text_async(self, prompt, model=None, task_type="chat", system_message=None, max_tokens=None):
        self.prompts.append(prompt)
        if system_message:
            self.prompts.append(system_message)
        return json.dumps(
            {
                "clarity_score": 7,
                "impact_score": 6,
                "skills_relevance_score": 8,
                "overall_feedback": "Clear and specific.",
                "technical_skills": ["Airflow"],
                "soft_skills": ["Mentoring"],
                "certifications": ["AWS Data Analytics"],
                "recommendations": "Keep going.",
            }
        )

    async def generate_text(self, prompt, model_type=None, task_type="general", max_tokens=None, system_message=None):
        return await self.generate_text_async(
            prompt, task_type=task_type, system_message=system_message, max_tokens=max_tokens
        )


class TripwireWebSearch:
    """Any call means someone's resume went to a search engine."""

    def __init__(self):
        self.queries: list[str] = []

    async def search(self, query, max_results=5):
        self.queries.append(query)
        raise AssertionError(f"web search must not run during an upload, got: {query}")


class StubResumeService:
    async def parse_resume_upload_no_save(self, upload_file, strategy="comprehensive"):
        return {"resume_id": None, "file_id": None, "parsed_data": parsed_resume()}


class FakeUpload:
    filename = FILE_NAME


class NoDB:
    def close(self):
        pass


@pytest.fixture
def agent(monkeypatch):
    """A bare agent with the parser, the model and the web stubbed, no DB."""
    import backend.utils.database as database

    def fake_get_db():
        yield NoDB()

    monkeypatch.setattr(database, "get_db", fake_get_db)

    a = object.__new__(ResumeProcessingAgent)
    a.resume_service = StubResumeService()
    a.llm_service = CapturingLLM()
    a.web_search_service = TripwireWebSearch()
    a.job_service = None  # the market path is not taken when job skills are given
    return a


@pytest.mark.asyncio
async def test_no_identifier_reaches_any_post_parse_prompt(agent):
    result = await agent.process_resume(
        FakeUpload(),
        db=None,
        save_to_db=False,
        target_job_title="Senior Data Engineer",
        job_data={"title": "Senior Data Engineer", "skills": ["Python", "SQL", "Airflow"]},
    )
    assert result["status"] == "success", result

    prompts = agent.llm_service.prompts
    assert prompts, "the pipeline made no model call at all; the test proves nothing"
    for prompt in prompts:
        for needle in IDENTIFIERS:
            assert needle not in prompt, f"{needle!r} reached a prompt:\n{prompt}"

    # The web was never consulted.
    assert agent.web_search_service.queries == []

    # The recruiter still gets the full parse.
    assert result["data"]["personal_info"]["name"] == NAME
    assert result["data"]["personal_info"]["email"] == EMAIL

    # And a report of what the models did not see.
    privacy = result["privacy"]
    assert "name" in privacy["identifying_fields_removed"]
    assert "email" in privacy["identifying_fields_removed"]
    assert privacy["web_lookups"] == 0
    assert privacy["model_calls_after_parse"] == len(POST_PARSE_MODEL_CALLS)


@pytest.mark.asyncio
async def test_published_model_call_list_matches_the_calls_made(agent):
    """One prompt per published step, so the transparency page cannot drift.

    A new post-parse model call has to be added to POST_PARSE_MODEL_CALLS,
    where it is published, or this fails.
    """
    await agent.process_resume(
        FakeUpload(),
        db=None,
        save_to_db=False,
        target_job_title="Senior Data Engineer",
        job_data={"title": "Senior Data Engineer", "skills": ["Python", "SQL"]},
    )
    # System messages are recorded alongside prompts; count the prompts only.
    user_prompts = [p for p in agent.llm_service.prompts if not p.startswith("You are")]
    assert len(user_prompts) == len(POST_PARSE_MODEL_CALLS)


@pytest.mark.asyncio
async def test_without_a_target_role_the_fit_commentary_does_not_run(agent):
    result = await agent.process_resume(FakeUpload(), db=None, save_to_db=False)
    assert result["privacy"]["model_calls_after_parse"] == len(POST_PARSE_MODEL_CALLS) - 1
    for prompt in agent.llm_service.prompts:
        for needle in IDENTIFIERS:
            assert needle not in prompt


# --- the published policy ---------------------------------------------------


def test_upload_policy_requires_a_token(client):
    assert client.get("/api/transparency/upload-policy").status_code == 401


def test_demo_role_can_read_the_upload_policy(demo_client):
    response = demo_client.get("/api/transparency/upload-policy")
    assert response.status_code == 200
    policy = response.json()

    assert policy["identifying_fields_removed"] == IDENTIFYING_FIELDS
    assert policy["dropped_keys"] == DROPPED_KEYS
    assert [c["name"] for c in policy["model_calls_after_parse"]] == [c["name"] for c in POST_PARSE_MODEL_CALLS]
    assert policy["web_lookups"] == 0
    assert policy["parse_writes_nothing"] is True
    assert policy["parser_providers"], "the parser's provider chain is published"


def test_policy_text_has_no_em_dashes(demo_client):
    body = demo_client.get("/api/transparency/upload-policy").text
    assert "—" not in body
