"""The golden question set: loading, casting, replaying and checking.

`assistant_golden.json` holds the questions. Each case is written against a
*cast* rather than fixed names, because the CI database only has the contract
suite's three people and two jobs while dev and prod carry the demo seed:

    {{cast:candidate}}   a candidate who has a parsed resume on file
    {{cast:job}}         an open job title

The CI test casts the contract seed (Ada Lovelace, Senior Data Engineer); the
live runner discovers a cast from whatever database it is pointed at.

A case has:

    id              short slug
    question        what the visitor typed (cast placeholders allowed)
    expected_tools  tools that must appear in the trace
    expected_any    at least one of these tools must appear (optional)
    forbidden_tools tools that must not appear; "*" means none at all
    checks          keyword arguments for assistant_checks.check_answer
    checks_by_outcome
                    extra checks keyed by outcome (see `outcome_of`), merged
                    over `checks` when that outcome happened
    replay.calls    the tool calls a stub provider makes, in order
    replay.reply    the answer the stub provider gives, as a template or a
                    dict of templates keyed by outcome (with "default")

Reply templates can pull from the tool results, so the replayed answer links
to real ids and quotes real numbers, which is what makes the checks bite:

    {{value:key}}             first value found under `key` in any result
    {{list:key}}              same, joined with commas
    {{dict:key}}              same, rendered as "k: v, k: v"
    {{link:candidate:Name}}   [Name](/candidates/<id>) from the results
    {{link:job:Title}}        [Title](/jobs/<id>) from the results
    {{links:candidates}}      every returned candidate, linked (max 5)
    {{links:jobs}}            every returned job, linked (max 8)

Outcomes (`outcome_of`): search_degraded, error, unavailable, elsewhere (a
location search that missed but found people in other places), empty, context
(every person found matched only in headline, company or skills, never in
their job title), default.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List

from evals.assistant_checks import check_answer, entities_in, find_entity_id

GOLDEN_PATH = Path(__file__).with_name("assistant_golden.json")

CAST_RE = re.compile(r"\{\{cast:(\w+)\}\}")
TEMPLATE_RE = re.compile(r"\{\{(value|list|dict|link|links):([^}]+)\}\}")


@dataclass
class Case:
    id: str
    question: str
    expected_tools: List[str] = field(default_factory=list)
    expected_any: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)
    checks: Dict[str, Any] = field(default_factory=dict)
    checks_by_outcome: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    replay_calls: List[Dict[str, Any]] = field(default_factory=list)
    replay_reply: Any = ""


def load_cases(path: Path = GOLDEN_PATH) -> List[Case]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for item in raw["cases"]:
        replay = item.get("replay", {})
        cases.append(
            Case(
                id=item["id"],
                question=item["question"],
                expected_tools=item.get("expected_tools", []),
                expected_any=item.get("expected_any", []),
                forbidden_tools=item.get("forbidden_tools", []),
                checks=item.get("checks", {}),
                checks_by_outcome=item.get("checks_by_outcome", {}),
                replay_calls=replay.get("calls", []),
                replay_reply=replay.get("reply", ""),
            )
        )
    return cases


def cast_text(text: str, cast: Dict[str, str]) -> str:
    def sub(m):
        key = m.group(1)
        if key not in cast:
            raise KeyError(f"golden case needs cast member {key!r}")
        return cast[key]

    return CAST_RE.sub(sub, text)


def cast_value(value: Any, cast: Dict[str, str]) -> Any:
    if isinstance(value, str):
        return cast_text(value, cast)
    if isinstance(value, list):
        return [cast_value(v, cast) for v in value]
    if isinstance(value, dict):
        return {k: cast_value(v, cast) for k, v in value.items()}
    return value


def outcome_of(results: List[Any]) -> str:
    """Which branch the tools took, for picking replies and extra checks."""
    dicts = [r for r in results if isinstance(r, dict)]
    if any(r.get("search_degraded") for r in dicts):
        return "search_degraded"
    if any("error" in r for r in dicts):
        return "error"
    # Only the salary tool reports a status; a job or candidate summary has
    # one too, but "open" or "hired" is data, not an outcome.
    if any(r.get("status") in ("unavailable", "error") for r in dicts):
        return "unavailable"
    if dicts:
        last = dicts[-1]
        if last.get("count") == 0 and last.get("candidates_elsewhere"):
            # A location search that missed but found people elsewhere: the
            # honest answer names them and where they are, which is a
            # different reply (and different checks) from a true miss.
            return "elsewhere"
        if last.get("count") == 0 or last.get("matches") == []:
            return "empty"
        candidates = last.get("candidates")
        if candidates and all(c.get("match_kind") == "context" for c in candidates):
            # Everyone found is related by industry or skill, not by role:
            # "any real estate agents?" answered with a data scientist at a
            # real estate marketplace. The honest reply leads with no.
            return "context"
    return "default"


def _first_value(results: List[Any], key: str) -> Any:
    def walk(value):
        if isinstance(value, dict):
            if key in value:
                return value[key]
            for v in value.values():
                found = walk(v)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for v in value:
                found = walk(v)
                if found is not None:
                    return found
        return None

    return walk(results)


def render_reply(template: Any, results: List[Any]) -> str:
    """Fill a reply template (or pick one by outcome) from the tool results."""
    if isinstance(template, dict):
        template = template.get(outcome_of(results), template.get("default", ""))
    entities = entities_in(results)

    def sub(m):
        kind, arg = m.group(1), m.group(2)
        if kind == "value":
            value = _first_value(results, arg)
            return "" if value is None else str(value)
        if kind == "list":
            value = _first_value(results, arg) or []
            return ", ".join(str(v) for v in value)
        if kind == "dict":
            value = _first_value(results, arg) or {}
            return ", ".join(f"{k}: {v}" for k, v in value.items())
        if kind == "link":
            entity_kind, name = arg.split(":", 1)
            table = "candidates" if entity_kind == "candidate" else "jobs"
            ident = find_entity_id(results, table, name)
            return f"[{name}](/{table}/{ident})" if ident else name
        if kind == "links":
            table = entities.candidates if arg == "candidates" else entities.jobs
            cap = 5 if arg == "candidates" else 8
            return ", ".join(f"[{name}](/{arg}/{ident})" for ident, name in list(table.items())[:cap])
        return m.group(0)

    return TEMPLATE_RE.sub(sub, str(template))


def checks_for(case: Case, results: List[Any], cast: Dict[str, str]) -> Dict[str, Any]:
    """The check_answer kwargs for this case, given what the tools returned."""
    merged: Dict[str, Any] = dict(case.checks)
    extra = case.checks_by_outcome.get(outcome_of(results), {})
    for key, value in extra.items():
        if isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = merged[key] + value
        else:
            merged[key] = value
    return cast_value(merged, cast)


def check_case(
    case: Case, text: str, results: List[Any], tools_used: List[str], cast: Dict[str, str]
) -> List[str]:
    failures = check_answer(
        text,
        results,
        tools_used,
        expected_tools=cast_value(case.expected_tools, cast),
        forbidden_tools=[t for t in case.forbidden_tools if t != "*"],
        **checks_for(case, results, cast),
    )
    if "*" in case.forbidden_tools and tools_used:
        failures.append(f"no tool call was expected, got {tools_used}")
    if case.expected_any and not set(case.expected_any) & set(tools_used):
        failures.append(f"none of {case.expected_any} was used (used {tools_used})")
    return failures


def replay_runner(case: Case, cast: Dict[str, str]) -> Callable:
    """A tool-loop runner that plays the case's recorded tool calls.

    Drop-in for an entry of tool_loop._RUNNERS: it narrates each call through
    the trace exactly as a real tier would, executes it against the real
    tools, and then answers from the reply template rendered over what the
    tools returned. The loop's result carries those returns as tool_results,
    already dash-normalised by execute_tool, which is what the checks read.
    """
    from backend.services.assistant_tools import execute_tool

    async def runner(settings, system, messages, tools, trace):
        results: List[Any] = []
        for call in case.replay_calls:
            name = call["tool"]
            args = cast_value(call.get("arguments", {}), cast)
            await trace.tool_started(name, args)
            result = await execute_tool(tools, name, args)
            await trace.tool_finished(name, args, result)
            results.append(result)
        return render_reply(cast_value(case.replay_reply, cast), results)

    return runner


def discover_cast(db) -> Dict[str, str]:
    """Pick a cast from a live database: a candidate with a resume, an open job."""
    from backend.models.models import Candidate, Job, Resume

    job = db.query(Job).filter(Job.status == "open").order_by(Job.id).first()
    if job is None:
        job = db.query(Job).order_by(Job.id).first()
    candidate = (
        db.query(Candidate)
        .join(Resume, Resume.candidate_id == Candidate.id)
        .filter(Resume.parsed_content.isnot(None))
        .order_by(Candidate.created_at)
        .first()
    )
    if job is None or candidate is None:
        raise RuntimeError("the database has no open job or no candidate with a parsed resume")
    return {
        "candidate": f"{candidate.first_name} {candidate.last_name}".strip(),
        "job": job.title,
    }
