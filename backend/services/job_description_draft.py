"""Draft a job overview and qualifications from the job's own fields (ATS Phase E).

The prompt is built from the structured fields a job writer typed and
nothing else: no candidate, resume, or note is ever read here. Each field
is still scrubbed with the upload de-identification rules, so contact
details pasted into a title by mistake stay on the server. The call goes
through LLMService, which routes via build_chain (ADR 0002); set
LLM_PROVIDER_ORDER_JOB_DESCRIPTION to route it separately.
"""
from __future__ import annotations

from typing import Optional

from backend.models.job_draft import JobDescriptionDraft, JobDraftRequest
from backend.services.assistant_tools import plain_dashes
from backend.services.llm_service import get_llm_service
from backend.services.resume_privacy import scrub_text

TASK_TYPE = "job_description"

SYSTEM_PROMPT = (
    "You write clear, inclusive job descriptions for a recruiting team. Use plain "
    "American English and short sentences. Do not use em dashes. Do not invent a "
    "company name, salary, benefits, or facts that were not given."
)


def build_prompt(request: JobDraftRequest) -> str:
    counts = {"name_mentions": 0, "emails": 0, "phones": 0, "links": 0}

    def clean(value: Optional[str]) -> str:
        return scrub_text((value or "").strip(), [], counts)

    lines = [f"Title: {clean(request.title)}"]
    if request.department:
        lines.append(f"Department: {clean(request.department)}")
    if request.experience_level:
        lines.append(f"Experience level: {clean(request.experience_level)}")
    if request.location_type:
        lines.append(f"Work arrangement: {clean(request.location_type)}")
    skills = [clean(skill) for skill in request.skills if skill and skill.strip()]
    if skills:
        lines.append("Key skills: " + ", ".join(skills))

    return (
        "Draft a job description for the role below.\n"
        "Write job_overview as two short paragraphs about what the person will do "
        "and why the work matters.\n"
        "Write required_qualifications as 4 to 7 lines, one requirement per line, "
        "with no bullet characters.\n"
        "Use only the facts given.\n\n" + "\n".join(lines)
    )


async def draft(request: JobDraftRequest, llm=None) -> JobDescriptionDraft:
    """Raises AllProvidersFailedError when no tier answers, ValueError on unusable output."""
    llm = llm or get_llm_service()
    data = await llm.generate_structured(
        build_prompt(request),
        JobDescriptionDraft,
        system_message=SYSTEM_PROMPT,
        max_tokens=900,
        task_type=TASK_TYPE,
    )
    parsed = JobDescriptionDraft.model_validate(data)
    return JobDescriptionDraft(
        job_overview=plain_dashes(parsed.job_overview).strip(),
        required_qualifications=plain_dashes(parsed.required_qualifications).strip(),
    )
