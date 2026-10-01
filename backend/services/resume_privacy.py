"""De-identifying a parsed resume before any model or service sees it again.

The parser has to read the whole resume once: extracting a name, an email and
a phone number is its job. Everything that runs *after* the parse (the quality
assessment, the skill suggestions, the fit commentary) is advisory text about
a profile, and none of it needs to know who the person is. So those steps get
a copy of the parse with the identifying fields removed and the free text
scrubbed, and the transparency page publishes exactly that from the constants
below rather than from a description that could drift.

Two reasons this matters beyond politeness:

* Those later prompts leave the machine. Per ADR 0002 they go to whichever
  provider is first in the chain, and a name plus an employer is enough to
  identify someone to a third party that never needed to know.
* A name carries gender and ethnicity signal. The quality scores feed the
  upload fit score, so a model that read the name could move a number that
  is shown to a recruiter as if it were about the resume.

Nothing here changes what is *stored* when an administrator saves a parse:
the pipeline keeps the full profile, because a recruiter has to be able to
contact the person. Parsing alone still writes nothing.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Tuple

# personal_info keys dropped from the de-identified copy. `summary` is the
# only key kept, scrubbed; `location` is dropped because no post-parse step
# reads it and a city narrows a name considerably.
IDENTIFYING_FIELDS: List[str] = [
    "name",
    "email",
    "phone",
    "address",
    "location",
    "linkedin",
    "github",
    "website",
]

# Top-level keys dropped outright. The raw text is the resume itself, and a
# file name is very often "<First>_<Last>_Resume.pdf".
DROPPED_KEYS: List[str] = ["raw_text", "file_name"]

# What the scrubber replaces inside every remaining string, in the order it
# runs. Published on the transparency page verbatim.
TEXT_PATTERNS_SCRUBBED: List[str] = [
    "the candidate's name, in full and each part on its own",
    "email addresses",
    "phone numbers",
    "links (http, www, linkedin.com and github.com paths)",
]

NAME_PLACEHOLDER = "the candidate"
EMAIL_PLACEHOLDER = "[email removed]"
PHONE_PLACEHOLDER = "[phone removed]"
LINK_PLACEHOLDER = "[link removed]"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Requires a 3-3-4 shape (optionally with a country code), so a date range
# such as "2019-2023" or a nine-digit employee count is left alone.
_PHONE_RE = re.compile(
    r"(?<![\w-])(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?![\w-])"
)
_LINK_RE = re.compile(
    r"https?://\S+|\bwww\.\S+|\b(?:linkedin|github)\.com/\S+", re.IGNORECASE
)


def _name_patterns(name: str) -> List[re.Pattern]:
    """The full name first, then each part of two or more characters.

    Parts are matched as whole words and case-insensitively, so "Priya" in a
    bullet is caught but "Priya" inside "Supriya" is not. A short part such as
    "Al" can collide with ordinary text; a lost word in an advisory prompt is
    the cheaper mistake.
    """
    name = (name or "").strip()
    if not name:
        return []
    patterns = [re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)]
    for part in re.split(r"[\s,.]+", name):
        part = part.strip("()'\"")
        if len(part) >= 2:
            patterns.append(re.compile(r"\b" + re.escape(part) + r"\b", re.IGNORECASE))
    return patterns


def scrub_text(text: str, name_patterns: List[re.Pattern], counts: Dict[str, int]) -> str:
    """Replace identifying patterns in one string, counting what was hit."""
    if not isinstance(text, str) or not text:
        return text
    for pattern in name_patterns:
        text, n = pattern.subn(NAME_PLACEHOLDER, text)
        counts["name_mentions"] += n
    text, n = _EMAIL_RE.subn(EMAIL_PLACEHOLDER, text)
    counts["emails"] += n
    text, n = _LINK_RE.subn(LINK_PLACEHOLDER, text)
    counts["links"] += n
    text, n = _PHONE_RE.subn(PHONE_PLACEHOLDER, text)
    counts["phones"] += n
    return text


def _scrub_value(value: Any, name_patterns: List[re.Pattern], counts: Dict[str, int]) -> Any:
    if isinstance(value, str):
        return scrub_text(value, name_patterns, counts)
    if isinstance(value, list):
        return [_scrub_value(item, name_patterns, counts) for item in value]
    if isinstance(value, dict):
        return {k: _scrub_value(v, name_patterns, counts) for k, v in value.items()}
    return value


def anonymize_parsed_resume(parsed: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A de-identified copy of a parse, plus a report of what was removed.

    The input is never mutated: the full parse still goes back to the
    recruiter, who needs the contact details. The report is what the upload
    screen shows under the result, so a visitor can see the de-identification
    happened on their file rather than take the transparency page's word.
    """
    if not isinstance(parsed, dict):
        return {}, _empty_report()

    safe = copy.deepcopy(parsed)
    personal = safe.get("personal_info")
    personal = personal if isinstance(personal, dict) else {}

    removed = [field for field in IDENTIFYING_FIELDS if personal.get(field)]
    name = personal.get("name") if isinstance(personal.get("name"), str) else ""
    name_patterns = _name_patterns(name)

    safe["personal_info"] = {"summary": personal.get("summary")} if personal.get("summary") else {}
    for key in DROPPED_KEYS:
        safe.pop(key, None)

    counts = {"name_mentions": 0, "emails": 0, "phones": 0, "links": 0}
    safe = _scrub_value(safe, name_patterns, counts)

    report = {
        "identifying_fields_removed": removed,
        "name_mentions_scrubbed": counts["name_mentions"],
        "emails_scrubbed": counts["emails"],
        "phones_scrubbed": counts["phones"],
        "links_scrubbed": counts["links"],
    }
    return safe, report


def _empty_report() -> Dict[str, Any]:
    return {
        "identifying_fields_removed": [],
        "name_mentions_scrubbed": 0,
        "emails_scrubbed": 0,
        "phones_scrubbed": 0,
        "links_scrubbed": 0,
    }
