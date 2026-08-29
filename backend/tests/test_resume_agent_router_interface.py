"""The agent method the /api/resume/parse router calls must accept what the router sends.

Found during Phase 3 wrap-up: the web demo posted `target_job_title` with a
resume, the router forwarded it as a keyword argument, and `process_resume()`
raised `unexpected keyword argument 'target_job_title'` — the one code path a
recruiter actually exercises. Worse, the method hard-coded the title to None
internally, so job-fit scoring was unreachable from the endpoint even before
the crash. These tests pin the router-facing signature and the pass-through.
"""
from __future__ import annotations

import pytest

from backend.services.agent_framework.agents.resume_processing_agent import (
    ResumeProcessingAgent,
)


def make_agent_with_stubbed_processing(captured: dict):
    """A bare agent whose file processing just records what it was asked to do.

    The stub mirrors the real `_process_single_file` signature deliberately: if
    it drifts, these tests fail, which is the entire point of the file.
    """
    agent = object.__new__(ResumeProcessingAgent)

    async def fake_process_single_file(
        file, target_job_title=None, job_skills=None, job_requirements=None
    ):
        captured["target_job_title"] = target_job_title
        captured["job_skills"] = job_skills
        captured["job_requirements"] = job_requirements
        return {"status": "success", "data": {"personal_info": {"name": "X"}}}

    agent._process_single_file = fake_process_single_file
    return agent


class FakeUpload:
    filename = "resume.pdf"


@pytest.mark.asyncio
async def test_process_resume_accepts_the_router_call_verbatim():
    """Exactly the call from backend/routers/resume.py — every kwarg included."""
    captured = {}
    agent = make_agent_with_stubbed_processing(captured)
    result = await agent.process_resume(
        FakeUpload(), db=None, save_to_db=False, candidate_id=None,
        target_job_title="Senior Software Engineer", job_data=None,
    )
    assert result["status"] == "success"
    assert captured["target_job_title"] == "Senior Software Engineer"


@pytest.mark.asyncio
async def test_process_resume_derives_title_from_job_data():
    """No explicit title, but a job object with one — same rule execute() uses."""
    captured = {}
    agent = make_agent_with_stubbed_processing(captured)
    await agent.process_resume(
        FakeUpload(), target_job_title=None, job_data={"title": "ML Engineer"},
    )
    assert captured["target_job_title"] == "ML Engineer"


@pytest.mark.asyncio
async def test_process_resume_forwards_a_real_requisitions_skills():
    """The whole point of passing a job rather than a title.

    If these stop reaching `_process_single_file`, the fit score silently falls
    back to the market estimate while the UI still claims it scored against the
    named role.
    """
    captured = {}
    agent = make_agent_with_stubbed_processing(captured)
    await agent.process_resume(
        FakeUpload(),
        job_data={
            "title": "ML Engineer",
            "skills": "Python,PyTorch,Kubernetes",
            "required_qualifications": "3+ years shipping models",
        },
    )
    assert captured["target_job_title"] == "ML Engineer"
    assert captured["job_skills"] == ["Python", "PyTorch", "Kubernetes"]
    assert captured["job_requirements"] == "3+ years shipping models"


@pytest.mark.asyncio
async def test_process_resume_sends_no_skills_when_the_job_lists_none():
    """None, not [], so the agent falls back instead of scoring against nothing."""
    captured = {}
    agent = make_agent_with_stubbed_processing(captured)
    await agent.process_resume(FakeUpload(), job_data={"title": "ML Engineer"})
    assert captured["job_skills"] is None


@pytest.mark.asyncio
async def test_quality_summary_survives_null_descriptions_and_skills():
    """The LLM sometimes emits "description": null; that cost the whole
    quality/suggestions/enrichment gather ('NoneType' is not subscriptable)."""
    agent = object.__new__(ResumeProcessingAgent)

    class FailingLLM:
        async def generate_text_async(self, *a, **k):
            raise RuntimeError("no LLM in unit tests")

    agent.llm_service = FailingLLM()
    assessment = await agent._assess_resume_quality(
        {
            "personal_info": {"name": "April Drake"},
            "experience": [{"title": "SWE", "company": "Uber", "description": None}],
            "skills": [{"name": None}, {"name": "Python"}],
        }
    )
    # Summary construction must not raise; the LLM failure falls back gracefully.
    assert "clarity_score" in assessment
