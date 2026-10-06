"""How a candidate found the job: one vocabulary for every way in (Track 2 Phase 3).

The add-candidate panel, the bulk uploader, "Consider for another role" and
the apply endpoint all record an application source from this list, so the
Reports page groups real channels instead of whatever each screen happened
to write ("direct", "resume_upload", "Direct").

The values are the CandidateSource enum plus `internal` (an employee or an
existing candidate moved to another role). The Alembic revision
c8e2f4a6b9d1 mapped older free-text values the same way `normalize` does.
"""
from __future__ import annotations

from typing import Optional

# Display order for pickers: the most common channels first.
SOURCE_LABELS: dict[str, str] = {
    "linkedin": "LinkedIn",
    "referral": "Referral",
    "company_website": "Company website",
    "indeed": "Indeed",
    "job_board": "Other job board",
    "agency": "Agency",
    "direct_application": "Applied directly",
    "internal": "Internal",
    "other": "Other",
}

APPLICATION_SOURCES = tuple(SOURCE_LABELS)
DEFAULT_SOURCE = "direct_application"
UNKNOWN_LABEL = "Not recorded"

# Free-text values written before the vocabulary existed.
LEGACY_SOURCES = {
    "direct": "direct_application",
    "resume_upload": "direct_application",
}


def normalize(value: Optional[str]) -> str:
    """A stored source for any input: known values kept, legacy mapped, the rest `other`.

    Blank means the caller did not say, which is the default channel.
    """
    text = (value or "").strip().lower()
    if not text:
        return DEFAULT_SOURCE
    if text in SOURCE_LABELS:
        return text
    return LEGACY_SOURCES.get(text, "other")


def label(value: Optional[str]) -> str:
    """'company_website' -> 'Company website'; NULL or blank -> 'Not recorded'."""
    text = (value or "").strip().lower()
    if not text or text == "unknown":
        return UNKNOWN_LABEL
    return SOURCE_LABELS.get(text, SOURCE_LABELS["other"])
