"""The assistant's answer as the visitor sees it.

Two rules the prompt states and the models do not reliably keep are enforced
here, deterministically, for every provider tier and both chat endpoints:

- no em or en dashes (the local 8B model writes salary ranges with them);
- every candidate or job a tool returned is a profile link when the answer
  names it (the local model links list entries but writes a single subject
  in bold: "**Senior Data Scientist** requires ..." rendered as bold text,
  not a link, so a visitor had nowhere to click).

Arguing with an 8B model about either is a losing game; rewriting the answer
is cheap and covers whatever model serves the turn.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from backend.services.assistant_tools import plain_dashes

LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
# The chat renderer (web/src/lib/chat-markdown.ts) matches **bold** and
# [label](href) as sibling tokens: a link inside a bold span is shown as the
# literal "[label](href)" text. So a bold span that ends up holding a link is
# unwrapped, and the link's own styling stands in for the emphasis.
BOLD_WITH_LINK_RE = re.compile(r"\*\*([^*\n]*\[[^\]\n]+\]\([^)\s]+\)[^*\n]*)\*\*")

MIN_NAME_CHARS = 3


def entities_in(results: Iterable[Any]) -> Dict[str, Dict[str, str]]:
    """Every candidate and job the tools returned: {"candidates": {id: name},
    "jobs": {id: title}}.

    Understands every shape the assistant tools produce: candidate summaries
    and search hits ({id, name}), job summaries and open_jobs entries
    ({id, title}), match_to_job ({job_id, job_title}), explain_match
    ({job: {id, title}, candidate: {id, name}}) and get_candidate_resume
    ({candidate, candidate_id}). evals/assistant_checks.py keeps its own copy
    on purpose: the checker is the independent judge of what this produces.
    """
    candidates: Dict[str, str] = {}
    jobs: Dict[str, str] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if "id" in value and isinstance(value.get("title"), str):
                jobs[str(value["id"])] = value["title"]
            elif "id" in value and isinstance(value.get("name"), str):
                candidates[str(value["id"])] = value["name"]
            if "job_id" in value and isinstance(value.get("job_title"), str):
                jobs[str(value["job_id"])] = value["job_title"]
            if "candidate_id" in value and isinstance(value.get("candidate"), str):
                candidates[str(value["candidate_id"])] = value["candidate"]
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(list(results))
    return {"candidates": candidates, "jobs": jobs}


def _protected_spans(text: str) -> List[Tuple[int, int]]:
    return [(m.start(), m.end()) for m in LINK_RE.finditer(text)]


def _inside(spans: List[Tuple[int, int]], start: int, end: int) -> bool:
    return any(start < b and end > a for a, b in spans)


PROFILE_HREF_RE = re.compile(r"^/(candidates|jobs)/([A-Za-z0-9_-]*)$")
_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(text: str) -> List[str]:
    return _WORD_RE.findall(re.sub(r"'s", "", text.lower()))


def _entity_named(label: str, table: Dict[str, str]) -> Optional[str]:
    """The one returned id whose name the label is, or a word-run of."""
    words = _words(label)
    if not words:
        return None
    hits = []
    for ident, name in table.items():
        name_words = _words(name)
        if any(name_words[i : i + len(words)] == words for i in range(len(name_words) - len(words) + 1)):
            hits.append(ident)
    return hits[0] if len(hits) == 1 else None


def repair_links(text: str, found: Dict[str, Dict[str, str]]) -> str:
    """Point a profile link whose id no tool returned at the entity its label
    names. The cloud model copies UUIDs by hand and drops or doubles a
    character now and then ("5f9a1a1a3c-..." for "5f9a1a3c-..."), and once
    wrote "/jobs/" with no id at all; both rendered as a dead link or plain
    text where the visitor expected a profile."""

    def fix(m):
        label, href = m.group(1), m.group(2)
        path = PROFILE_HREF_RE.match(href)
        if not path:
            return m.group(0)
        kind, ident = path.group(1), path.group(2)
        table = found[kind]
        if ident in table:
            return m.group(0)
        repaired = _entity_named(label, table)
        return f"[{label}](/{kind}/{repaired})" if repaired else m.group(0)

    return LINK_RE.sub(fix, text)


def linkify(text: str, results: Iterable[Any]) -> str:
    """Link the first plain mention of each returned candidate or job, and
    repair links whose id no tool returned.

    A name the model already linked (any label, same id) is left alone, as is
    anything inside an existing link. Longer names go first so "Senior Data
    Scientist" is linked as itself and never as a "Data Scientist" inside it.
    Matching is whole-word and case-insensitive; the visitor sees the text
    the model wrote, now clickable.
    """
    if not text:
        return text
    found = entities_in(results)
    text = repair_links(text, found)
    targets = [(name, f"/candidates/{ident}") for ident, name in found["candidates"].items()]
    targets += [(title, f"/jobs/{ident}") for ident, title in found["jobs"].items()]
    targets = [(n.strip(), href) for n, href in targets if len(n.strip()) >= MIN_NAME_CHARS]
    targets.sort(key=lambda t: len(t[0]), reverse=True)

    spans = _protected_spans(text)
    linked = {href for _, href in LINK_RE.findall(text)}
    for name, href in targets:
        if href in linked:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.IGNORECASE)
        for m in pattern.finditer(text):
            if _inside(spans, m.start(), m.end()):
                continue
            replacement = f"[{m.group(0)}]({href})"
            text = text[: m.start()] + replacement + text[m.end() :]
            delta = len(replacement) - (m.end() - m.start())
            spans = [(a, b) if b <= m.start() else (a + delta, b + delta) for a, b in spans]
            spans.append((m.start(), m.start() + len(replacement)))
            linked.add(href)
            break

    return BOLD_WITH_LINK_RE.sub(r"\1", text)


def finalize_answer(text: str, results: Iterable[Any] = ()) -> str:
    """What both chat endpoints send back: dashes normalised, names linked."""
    return linkify(plain_dashes(text or ""), results)
