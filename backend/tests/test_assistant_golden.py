"""The golden assistant questions, replayed in CI without a model.

Regression net from the 2026-09-30 assistant audit (PR 3). Each case in
evals/assistant_golden.json runs through the real tool loop with a stub
provider that plays the recorded tool calls against the real tools and the
contract seed, then answers from a template filled with what the tools
returned. The checks in evals/assistant_checks.py then hold that answer to
the same rules the live runner (evals/chat_smoke.py) applies to a real model:
no dashes, profile links only to returned ids, the expected tools, and the
honest wording on the paths where data is missing.

What this catches: a tool whose result shape changes so the answer can no
longer link or count from it, a tool that starts erroring on a golden
question, a prompt or tool note that grows an em dash, and a checker that
would wave through a fabricated link. What it does not catch: a model that
picks the wrong tool. That is the live runner's job.
"""
from __future__ import annotations

import asyncio
import re

import pytest

from backend.routers.assistant import SYSTEM_PROMPT
from backend.services import tool_loop as tl
from backend.services.assistant_answer import finalize_answer
from backend.services.assistant_tools import (
    RESUME_FRAMING_NOTE,
    SALARY_UNAVAILABLE_NOTE,
    SEARCH_DEGRADED_NOTE,
    build_assistant_tools,
    location_miss_note,
    context_match_note,
    more_at_stage_note,
    no_match_note,
    nobody_at_stage_note,
    partial_match_note,
    unknown_stage_note,
)
from backend.services.market_research_service import MarketResearchService
from backend.services.tool_loop import run_tool_loop
from evals.assistant_checks import DASH_RE, check_answer, entities_in
from evals.assistant_golden import (
    cast_text,
    check_case,
    load_cases,
    outcome_of,
    render_reply,
    replay_runner,
)

CASES = load_cases()

# The contract seed (conftest.py): a candidate with a parsed resume and an
# open job. Prod and dev use the demo seed; the live runner discovers its own.
CAST = {"candidate": "Ada Lovelace", "job": "Senior Data Engineer"}


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _Settings:
    ollama_chat_enabled = True
    ollama_chat_model = "replay"
    openrouter_api_key = ""
    openrouter_enabled = False
    anthropic_api_key = ""
    anthropic_enabled = False
    llm_provider_order = "ollama"
    assistant_turn_budget_s = 120.0


class _NoSearch:
    """Prod has no search keys; the replay must not depend on the dev .env."""

    has_backend = False

    async def search(self, query, max_results=5):
        raise AssertionError("no web search during golden replay")


class _NoLLM:
    async def generate_text_async(self, *args, **kwargs):
        raise AssertionError("no analysis LLM during golden replay")


@pytest.fixture(scope="module")
def golden_tools(db_session, seed):
    """The real assistant tools bound to the seeded session, with the market
    service pinned to the keyless path and every result recorded."""
    from backend.services.service_registry import get_registry

    registry = get_registry()
    previous = registry._market_research_service
    registry._market_research_service = MarketResearchService(_NoSearch(), _NoLLM())
    try:
        yield build_assistant_tools(db_session)
    finally:
        registry._market_research_service = previous


_REPLAYS = {}


def _replay(case, tools, monkeypatch):
    """Replay a case once per module: under an unreachable Ollama the matching
    cases pay a failed embedding call per candidate, which on Windows is four
    seconds each."""
    if case.id not in _REPLAYS:
        monkeypatch.setitem(tl._RUNNERS, "ollama", replay_runner(case, CAST))
        result = run(
            run_tool_loop(
                _Settings(),
                system=SYSTEM_PROMPT,
                message=cast_text(case.question, CAST),
                tools=tools,
            )
        )
        _REPLAYS[case.id] = (result, result.tool_results)
    return _REPLAYS[case.id]


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_golden_case_replays_clean(case, golden_tools, monkeypatch):
    result, results = _replay(case, golden_tools, monkeypatch)
    tools_used = [t["tool"] for t in result.tool_trace]
    assert tools_used == [c["tool"] for c in case.replay_calls]
    # The endpoints finalise the answer (dashes, links) before a visitor sees
    # it, so the checks judge the finalised text, as the live runner does.
    answer = finalize_answer(result.text, results)
    failures = check_case(case, answer, results, tools_used, CAST)
    assert not failures, (
        f"{case.id} ({outcome_of(results)}): {failures}\nanswer: {answer!r}\nresults: {results!r}"
    )


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_golden_tool_results_are_visitor_safe(case, golden_tools, monkeypatch):
    """Whatever a tool says back to the model may be repeated to the visitor
    word for word (the local model does), so notes and errors follow the
    same dash rule as the answer, and a golden question never trips an
    unexpected tool error."""
    _, results = _replay(case, golden_tools, monkeypatch)
    for result in results:
        for key in ("note", "error", "reason", "message"):
            value = result.get(key) if isinstance(result, dict) else None
            if isinstance(value, str):
                assert not DASH_RE.search(value), f"{case.id}: {key} carries a dash: {value!r}"
    if case.id != "unknown-job":
        errors = [r["error"] for r in results if isinstance(r, dict) and "error" in r]
        assert not errors, f"{case.id}: unexpected tool error {errors}"


def test_golden_set_covers_every_tool():
    """A tool nobody asks about in the golden set is a tool nothing checks."""
    tools = {t.name for t in build_assistant_tools(None)}
    replayed = {c["tool"] for case in CASES for c in case.replay_calls}
    assert tools <= replayed, f"tools with no golden question: {sorted(tools - replayed)}"


class TestPromptHygiene:
    """The rules the answers are held to start with the text the model reads."""

    def test_system_prompt_has_no_dashes(self):
        assert not DASH_RE.search(SYSTEM_PROMPT)

    def test_tool_descriptions_and_notes_have_no_dashes(self):
        for tool in build_assistant_tools(None):
            assert not DASH_RE.search(tool.description), tool.name
        for note in (RESUME_FRAMING_NOTE, SALARY_UNAVAILABLE_NOTE, SEARCH_DEGRADED_NOTE):
            assert not DASH_RE.search(note)

    NOTES = (
        RESUME_FRAMING_NOTE,
        SALARY_UNAVAILABLE_NOTE,
        SEARCH_DEGRADED_NOTE,
        location_miss_note("Seattle", "Python engineers"),
        no_match_note("Python engineers"),
        partial_match_note("Python engineers"),
        context_match_note("Python engineers"),
        unknown_stage_note("astrology"),
        nobody_at_stage_note(["Offer", "Offer accepted"]),
        more_at_stage_note(40, 15),
    )

    def test_notes_read_as_sentences_to_a_visitor(self):
        # The local model parrots notes verbatim, so no note may address the
        # model ("tell the user", "do not") at all. The search tool's location
        # and weak-match notes did until 2026-09-30.
        for note in self.NOTES:
            assert not re.search(r"\b(tell the user|do not|never|you must)\b", note, re.I), note
            assert not DASH_RE.search(note), note


class TestChecksCatchWhatTheyExistFor:
    """The checker is only worth running live if it actually fails bad answers."""

    RESULTS = [
        {"candidates": [{"id": "c-1", "name": "Ada Lovelace", "similarity": 0.7}], "count": 1},
        {"job_id": 7, "job_title": "Senior Data Engineer", "matches": [{"id": "c-1", "name": "Ada Lovelace", "match_score": 81.0}]},
    ]

    def test_entities_are_collected_from_every_shape(self):
        found = entities_in(
            self.RESULTS
            + [
                {"job": {"id": 9, "title": "ML Engineer"}, "candidate": {"id": "c-2", "name": "Grace Hopper"}},
                {"candidate": "Alan Turing", "candidate_id": "c-3", "parsed_content": "..."},
                {"error": "nope", "open_jobs": [{"id": 11, "title": "Product Manager"}]},
            ]
        )
        assert found.candidates == {"c-1": "Ada Lovelace", "c-2": "Grace Hopper", "c-3": "Alan Turing"}
        assert found.jobs == {"7": "Senior Data Engineer", "9": "ML Engineer", "11": "Product Manager"}

    def test_clean_answer_passes(self):
        text = "[Ada Lovelace](/candidates/c-1) is the top match for [Senior Data Engineer](/jobs/7) at 81%."
        assert check_answer(text, self.RESULTS, ["match_to_job"], expected_tools=["match_to_job"]) == []

    def test_dash_is_a_failure(self):
        failures = check_answer("Ada Lovelace — top match", self.RESULTS, [])
        assert any("dash" in f for f in failures)

    def test_link_to_unknown_id_is_a_failure(self):
        failures = check_answer("[Bob](/candidates/c-99) fits.", self.RESULTS, [])
        assert any("no tool returned" in f for f in failures)

    def test_link_label_must_name_the_entity(self):
        failures = check_answer("[Grace Hopper](/candidates/c-1) fits.", self.RESULTS, [])
        assert any("does not name" in f for f in failures)

    def test_first_name_only_label_is_fine(self):
        assert check_answer("[Ada](/candidates/c-1) fits.", self.RESULTS, []) == []

    def test_offsite_link_is_a_failure(self):
        failures = check_answer("[Ada](https://example.com/ada)", self.RESULTS, [])
        assert any("not a profile path" in f for f in failures)

    def test_missing_expected_tool_and_forbidden_tool(self):
        failures = check_answer(
            "x", self.RESULTS, ["search_candidates"], expected_tools=["match_to_job"], forbidden_tools=["search_candidates"]
        )
        assert len(failures) == 2

    def test_numbers_must_come_from_results(self):
        results = [{"total_candidates": 42, "open_jobs": 3, "candidates_by_status": {"active": 40, "hired": 2}}]
        assert check_answer("42 candidates, 3 open jobs, 40 active and 2 hired.", results, [], numbers_from_results=True) == []
        failures = check_answer("There are 57 candidates.", results, [], numbers_from_results=True)
        assert any("57" in f for f in failures)

    def test_ids_inside_links_are_not_counted_as_numbers(self):
        results = [{"open_jobs": 1, "jobs": [{"id": 7, "title": "Senior Data Engineer"}]}]
        text = "1 open job: [Senior Data Engineer](/jobs/7)."
        assert check_answer(text, results, [], numbers_from_results=True) == []

    def test_an_id_does_not_license_a_count(self):
        # A job with id 7 used to make "7 open jobs" pass.
        results = [{"open_jobs": 1, "jobs": [{"id": 7, "title": "Senior Data Engineer"}], "job_id": 9}]
        failures = check_answer("7 open jobs and 9 more.", results, [], numbers_from_results=True)
        assert [f for f in failures if "number 7" in f] and [f for f in failures if "number 9" in f]

    def test_sentence_final_and_formatted_numbers_are_checked(self):
        results = [{"total_candidates": 42, "open_jobs": 3}]
        # "57." at the end of a sentence used to slip past the checker.
        failures = check_answer("Total candidates: 57. Open jobs: 3.", results, [], numbers_from_results=True)
        assert any("number 57" in f for f in failures)
        failures = check_answer("There are 2,000 candidates.", results, [], numbers_from_results=True)
        assert any("number 2,000" in f for f in failures)
        # Scores, money, decimals and model names are not counts.
        clean = "42 candidates. Top score 81%, budget $80,000, 3.5 years, served by qwen3:8b."
        assert check_answer(clean, results, [], numbers_from_results=True) == []

    def test_link_label_must_not_be_a_longer_or_shorter_title(self):
        # Character-substring agreement let both directions through.
        results = [{"jobs": [{"id": 7, "title": "Data Engineer"}, {"id": 8, "title": "Senior Data Engineer"}]}]
        failures = check_answer("[Senior Data Engineer](/jobs/7) is open.", results, [])
        assert any("does not name" in f for f in failures)
        failures = check_answer("[Data Engineer](/jobs/8) is open.", results, [])
        assert any("is 'Data Engineer', but /jobs/8" in f for f in failures)
        assert check_answer("[Senior Data Engineer](/jobs/8) and [Data Engineer](/jobs/7).", results, []) == []
        assert check_answer("[the Senior Data Engineer role](/jobs/8) is open.", results, []) == []

    def test_last_name_and_possessive_labels_are_fine(self):
        text = "[Lovelace](/candidates/c-1) and [Ada Lovelace's](/candidates/c-1) resume."
        assert check_answer(text, self.RESULTS, []) == []
        failures = check_answer("[Ada Hopper](/candidates/c-1) fits.", self.RESULTS, [])
        assert any("does not name" in f for f in failures)

    def test_reply_template_links_real_ids(self):
        text = render_reply("Top: {{links:candidates}} for {{link:job:Senior Data Engineer}}.", self.RESULTS)
        assert text == "Top: [Ada Lovelace](/candidates/c-1) for [Senior Data Engineer](/jobs/7)."

    def test_reply_template_picks_by_outcome(self):
        template = {"default": "found", "error": "none", "search_degraded": "down"}
        assert render_reply(template, [{"error": "No job"}]) == "none"
        assert render_reply(template, [{"search_degraded": True, "candidates": []}]) == "down"
        assert render_reply(template, [{"count": 2}]) == "found"
        assert outcome_of([{"status": "unavailable"}]) == "unavailable"

    def test_context_only_search_is_its_own_outcome(self):
        ctx = {"count": 1, "candidates": [{"id": "c-1", "name": "Elena", "match_kind": "context", "similarity": 0.6}]}
        assert outcome_of([ctx]) == "context"
        mixed = {"count": 2, "candidates": [dict(ctx["candidates"][0]), {"id": "c-2", "name": "Ada", "match_kind": "role"}]}
        assert outcome_of([mixed]) == "default"
        template = {"default": "x", "context": "No. Related only: {{links:candidates}}"}
        assert render_reply(template, [ctx]) == "No. Related only: [Elena](/candidates/c-1)"

    def test_location_miss_with_people_elsewhere_is_its_own_outcome(self):
        # The "empty" reply claimed the unfiltered search found nobody too,
        # while candidates_elsewhere listed the people it found.
        miss = {"count": 0, "candidates": [], "location_filter": "west coast"}
        assert outcome_of([miss]) == "empty"
        assert outcome_of([dict(miss, candidates_elsewhere=[])]) == "empty"
        found = [dict(miss, candidates_elsewhere=[{"id": "c-1", "name": "Ada Lovelace", "similarity": 0.7}])]
        assert outcome_of(found) == "elsewhere"
        template = {"default": "x", "elsewhere": "{{links:candidates}}"}
        assert render_reply(template, found) == "[Ada Lovelace](/candidates/c-1)"
