"""A short committee brief from an application's interview feedback (Track 2 Phase 6).

Follows job_description_draft.py: one LLMService call with its own task
type (routable with LLM_PROVIDER_ORDER_FEEDBACK_SUMMARY, ADR 0002),
structured output, dashes normalized on the way out.

What the model reads, and what it never does:

- Submitted feedback only: rating, recommendation, notes, and the stage it
  was given for. Drafts are their author's alone (Track 2 Phase 4) and never
  reach a prompt.
- Never the match score, the resume, or anything else about the candidate.
- No names. The candidate becomes "the candidate", each interviewer with
  submitted feedback becomes "Interviewer 1..n" in stage order, and anyone
  else on the application becomes "a colleague". Emails, phones and links
  are scrubbed with the upload de-identification rules (resume_privacy).

The brief is generated on request and never stored, so it adds no candidate
data table (and nothing to erase, export, or retain).
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from backend.models.feedback import FeedbackSummaryDraft
from backend.models.models import ApplicationStage, Feedback, Interview, JobApplication
from backend.services.assistant_tools import plain_dashes
from backend.services.feedback_service import SUBMITTED, candidate_name
from backend.services.llm_service import get_llm_service
from backend.services.resume_privacy import NAME_PLACEHOLDER, name_parts, scrub_text

TASK_TYPE = "feedback_summary"
MIN_SUBMISSIONS = 2
MAX_POINTS = 5

RECOMMENDATION_WORDS = {
    "strong_hire": "Strong hire",
    "hire": "Hire",
    "no_hire": "No hire",
    "strong_no_hire": "Strong no hire",
}

SYSTEM_PROMPT = (
    "You summarize interview feedback for a hiring committee. Use only what the "
    "interviewers wrote. Do not decide whether to hire, do not add facts, and do not "
    "comment on age, gender, health, family, religion, ethnicity, or any other "
    "personal trait. Refer to interviewers as Interviewer 1, Interviewer 2, and so on. "
    "Use plain American English and short sentences. Do not use em dashes."
)

COLLEAGUE = "a colleague"

Entry = tuple[ApplicationStage, Interview, Feedback]


def submitted_entries(application: JobApplication) -> list[Entry]:
    """Every submitted feedback form on the application, in stage order."""
    rows = sorted(application.stages, key=lambda r: (r.stage.position, r.id))
    entries = []
    for row in rows:
        for interview in sorted(row.interviews, key=lambda i: i.id):
            feedback = interview.feedback
            if feedback is not None and feedback.status == SUBMITTED:
                entries.append((row, interview, feedback))
    return entries


def _interviewer_numbers(entries: Iterable[Entry]) -> dict[str, int]:
    """One number per person, so someone who ran two rounds is one voice."""
    numbers: dict[str, int] = {}
    for _, interview, _ in entries:
        numbers.setdefault(interview.interviewer_id, len(numbers) + 1)
    return numbers


def _name_scrubber(replacements: list[tuple[str, str]]):
    """One pass over every name at once, longest first, so "Interviewer 1"
    written in for one person is never re-matched by another person's name."""
    lookup: dict[str, str] = {}
    for name, replacement in replacements:
        for part in name_parts(name):
            lookup.setdefault(part.lower(), replacement)
    if not lookup:
        return lambda text: text
    alternation = "|".join(re.escape(k) for k in sorted(lookup, key=len, reverse=True))
    combined = re.compile(r"\b(?:" + alternation + r")\b", re.IGNORECASE)
    return lambda text: combined.sub(lambda m: lookup[m.group(0).lower()], text)


_HIRE_SIDE = {"strong_hire", "hire"}


def tally(entries: list[Entry]) -> str:
    """The recommendations and rating range, counted here rather than by the
    model: the local model missed a hire / no hire split in the Phase 6 eval."""
    counts = {key: 0 for key in RECOMMENDATION_WORDS}
    for _, _, feedback in entries:
        if feedback.recommendation in counts:
            counts[feedback.recommendation] += 1
    parts = [f"{n} {RECOMMENDATION_WORDS[key].lower()}" for key, n in counts.items() if n]
    ratings = sorted(f.rating for _, _, f in entries if f.rating is not None)
    if ratings and ratings[0] == ratings[-1]:
        parts.append(f"every rating {ratings[0]} of 5")
    elif ratings:
        parts.append(f"ratings from {ratings[0]} to {ratings[-1]} of 5")
    return ", ".join(parts).capitalize() + "." if parts else ""


def split_note(entries: list[Entry]) -> Optional[str]:
    """A disagreement the brief must carry when some say hire and some do not."""
    recommendations = [f.recommendation for _, _, f in entries if f.recommendation]
    hire = sum(1 for r in recommendations if r in _HIRE_SIDE)
    if 0 < hire < len(recommendations):
        return f"The recommendations are split: {hire} hire or strong hire, {len(recommendations) - hire} against."
    return None


def build_prompt(application: JobApplication, entries: list[Entry]) -> str:
    numbers = _interviewer_numbers(entries)
    replacements: list[tuple[str, str]] = []
    candidate = application.candidate
    if candidate is not None:
        replacements.append((candidate_name(candidate), NAME_PLACEHOLDER))
    by_id = {interview.interviewer_id: interview.interviewer for _, interview, _ in entries}
    for user_id, number in numbers.items():
        user = by_id.get(user_id)
        if user is not None and user.name:
            replacements.append((user.name, f"Interviewer {number}"))
    for row in application.stages:
        for interview in row.interviews:
            if interview.interviewer_id not in numbers and interview.interviewer and interview.interviewer.name:
                replacements.append((interview.interviewer.name, COLLEAGUE))
    job = application.job
    if job is not None:
        for name in (job.hiring_manager, job.recruiter):
            if name:
                replacements.append((name, COLLEAGUE))
    scrub_names = _name_scrubber(replacements)
    counts = {"name_mentions": 0, "emails": 0, "phones": 0, "links": 0}

    def clean(text: Optional[str]) -> str:
        return scrub_text(scrub_names((text or "").strip()), [], counts)

    blocks = []
    for row, interview, feedback in entries:
        recommendation = RECOMMENDATION_WORDS.get(feedback.recommendation or "", "none given")
        rating = f"{feedback.rating} of 5" if feedback.rating is not None else "none given"
        notes = clean(feedback.notes) or "(no notes)"
        blocks.append(
            f"Interviewer {numbers[interview.interviewer_id]}, {clean(row.stage.name)} round. "
            f"Rating: {rating}. Recommendation: {recommendation}.\nNotes: {notes}"
        )

    return (
        f"Below are {len(entries)} submitted interview feedback forms for one candidate.\n"
        "Write a short brief for the hiring committee:\n"
        "- themes: 2 to 4 points that came up across the interviews.\n"
        "- agreements: where the interviewers agree.\n"
        "- disagreements: where their ratings or views differ. Leave it empty if they do not.\n"
        "- open_questions: what is still unknown and worth checking in a later round.\n"
        "Each point is one sentence. Name the interviewer when a point comes from one person.\n\n"
        + f"Tally: {tally(entries)}\n\n"
        + "\n\n".join(blocks)
    )


def _points(items: list[str]) -> list[str]:
    out = []
    for item in items:
        text = plain_dashes(str(item)).strip().lstrip("-*• ").strip()
        if text:
            out.append(text)
    return out[:MAX_POINTS]


async def summarize(prompt: str, llm=None, split: Optional[str] = None) -> FeedbackSummaryDraft:
    """Raises AllProvidersFailedError when no tier answers, ValueError on unusable output.

    `split` (from split_note) is added to the disagreements if the model
    left them empty, so a split panel never reads as a consensus.
    """
    llm = llm or get_llm_service()
    data = await llm.generate_structured(
        prompt,
        FeedbackSummaryDraft,
        system_message=SYSTEM_PROMPT,
        max_tokens=900,
        task_type=TASK_TYPE,
    )
    parsed = FeedbackSummaryDraft.model_validate(data)
    summary = FeedbackSummaryDraft(
        themes=_points(parsed.themes),
        agreements=_points(parsed.agreements),
        disagreements=_points(parsed.disagreements),
        open_questions=_points(parsed.open_questions),
    )
    if not (summary.themes or summary.agreements or summary.disagreements or summary.open_questions):
        raise ValueError("The model returned an empty summary.")
    if split and not summary.disagreements:
        summary.disagreements = [split]
    return summary
