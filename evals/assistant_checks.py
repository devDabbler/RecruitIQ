"""Checks an assistant answer has to pass, whoever produced it.

Shared by the CI replay test (backend/tests/test_assistant_golden.py), which
runs the golden questions through a stub provider that replays recorded tool
calls, and by the live runner (evals/chat_smoke.py), which asks the real model
tiers the same questions against the dev database. The checks only look at
the answer text and the tool results the tools actually returned, so the
same rules apply in both places:

- no em or en dashes (a hard formatting rule for everything a visitor sees);
- every profile link points at an id some tool returned, and its label names
  that entity (a link is the assistant's claim that a person or job exists);
- the tools the case expects were used, and the ones it forbids were not;
- per-case must-mention strings and forbidden patterns.

Nothing here imports the backend: it is plain text and dicts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

DASH_RE = re.compile("[—–]")
LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
# Mirrors INTERNAL_HREF in web/src/lib/chat-markdown.ts: anything else renders
# as plain text in the chat bubble, so it is a broken claim, not a link.
INTERNAL_HREF_RE = re.compile(r"^/(candidates|jobs)/([A-Za-z0-9_-]+)$")
INT_RE = re.compile(r"(?<![\w.$/-])(\d+)(?![\w.%-])")


@dataclass
class Entities:
    """Every candidate and job the tools returned, keyed by id."""

    candidates: Dict[str, str] = field(default_factory=dict)
    jobs: Dict[str, str] = field(default_factory=dict)

    def ids(self) -> Dict[str, Dict[str, str]]:
        return {"candidates": self.candidates, "jobs": self.jobs}


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)


def entities_in(results: Iterable[Any]) -> Entities:
    """Collect the entities from any mix of tool results.

    Understands every shape the assistant tools produce: candidate summaries
    and search hits ({id, name}), job summaries and open_jobs entries
    ({id, title}), match_to_job ({job_id, job_title} plus matches[]), explain_match
    ({job: {id, title}, candidate: {id, name}}) and get_candidate_resume
    ({candidate, candidate_id}).
    """
    found = Entities()
    for d in _walk(list(results)):
        if "id" in d and isinstance(d.get("title"), str):
            found.jobs[str(d["id"])] = d["title"]
        elif "id" in d and isinstance(d.get("name"), str):
            found.candidates[str(d["id"])] = d["name"]
        if "job_id" in d and isinstance(d.get("job_title"), str):
            found.jobs[str(d["job_id"])] = d["job_title"]
        if "candidate_id" in d and isinstance(d.get("candidate"), str):
            found.candidates[str(d["candidate_id"])] = d["candidate"]
    return found


def numbers_in(results: Iterable[Any]) -> set:
    """Every integer value anywhere in the results (floats rounded)."""
    numbers = set()

    def visit(value: Any):
        if isinstance(value, bool):
            return
        if isinstance(value, int):
            numbers.add(value)
        elif isinstance(value, float):
            numbers.add(int(round(value)))
        elif isinstance(value, dict):
            for v in value.values():
                visit(v)
        elif isinstance(value, list):
            for v in value:
                visit(v)

    visit(list(results))
    return numbers


def links_in(text: str) -> List[Tuple[str, str]]:
    return [(label, href) for label, href in LINK_RE.findall(text)]


def strip_links(text: str) -> str:
    return LINK_RE.sub(lambda m: m.group(1), text)


def _names_agree(label: str, name: str) -> bool:
    a, b = label.strip().lower(), name.strip().lower()
    return bool(a) and (a in b or b in a)


def check_answer(
    text: str,
    results: List[Any],
    tools_used: List[str],
    *,
    expected_tools: Iterable[str] = (),
    forbidden_tools: Iterable[str] = (),
    must_mention: Iterable[str] = (),
    must_match: Iterable[str] = (),
    must_not_match: Iterable[str] = (),
    numbers_from_results: bool = False,
    require_link: bool = False,
) -> List[str]:
    """Return the list of failures (empty means the answer passed)."""
    failures: List[str] = []

    if DASH_RE.search(text):
        failures.append("answer contains an em or en dash")

    used = set(tools_used)
    missing = [t for t in expected_tools if t not in used]
    if missing:
        failures.append(f"expected tools not used: {missing} (used {sorted(used)})")
    banned = [t for t in forbidden_tools if t in used]
    if banned:
        failures.append(f"forbidden tools used: {banned}")

    entities = entities_in(results)
    links = links_in(text)
    if require_link and not links:
        failures.append("answer has no profile link")
    for label, href in links:
        m = INTERNAL_HREF_RE.match(href)
        if not m:
            failures.append(f"link {href!r} is not a profile path")
            continue
        kind, ident = m.group(1), m.group(2)
        known = entities.ids()[kind]
        if ident not in known:
            failures.append(f"link {href!r} points at an id no tool returned")
        elif not _names_agree(label, known[ident]):
            failures.append(f"link label {label!r} does not name {known[ident]!r} ({href})")

    lowered = text.lower()
    for phrase in must_mention:
        if phrase.lower() not in lowered:
            failures.append(f"answer does not mention {phrase!r}")
    for pattern in must_match:
        if not re.search(pattern, text, re.IGNORECASE):
            failures.append(f"answer does not match required pattern {pattern!r}")
    for pattern in must_not_match:
        if re.search(pattern, text, re.IGNORECASE):
            failures.append(f"answer matches forbidden pattern {pattern!r}")

    if numbers_from_results:
        allowed = numbers_in(results)
        for raw in INT_RE.findall(strip_links(text)):
            if int(raw) not in allowed:
                failures.append(f"number {raw} appears in the answer but in no tool result")

    return failures


def find_entity_id(results: List[Any], kind: str, name: str) -> Optional[str]:
    """The id of the returned candidate or job called `name`, if any."""
    table = entities_in(results).ids()[kind]
    for ident, known in table.items():
        if known.strip().lower() == name.strip().lower():
            return ident
    return None
