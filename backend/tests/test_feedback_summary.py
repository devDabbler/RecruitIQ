"""AI summary of an application's interview feedback (Track 2 Phase 6).

The LLM is always mocked here; the live check is in the PR description.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import feedback_service as fs
from backend.services import feedback_summary as summaries
from backend.services.llm.base import AllProvidersFailedError
from backend.tests.phase_e_helpers import make_application, staff_client, staff_user
from backend.utils.auth import create_access_token


class FakeLLM:
    def __init__(self, data=None, error=None):
        self.data = data or {
            "themes": ["Strong systems thinking — across both rounds.", "  "],
            "agreements": ["Both interviewers rate communication highly."],
            "disagreements": [],
            "open_questions": ["- How they handle on-call load."],
        }
        self.error = error
        self.calls = []

    async def generate_structured(self, prompt, schema, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error:
            raise self.error
        return self.data


def _first_round(application):
    return next(r for r in application.stages if r.stage.key == "resume_submitted")


@pytest.fixture
def panel(db_session):
    """Mira Quillfeather, two submitted forms, one draft. Committed, like the
    other Phase E fixtures, so a refused request cannot roll them away."""
    _, application = make_application(db_session, first_name="Mira", last_name="Quillfeather")
    odette = staff_user(db_session, "hiring_team", name="Odette Varga")
    bram = staff_user(db_session, "interviewer", name="Bram Kettering")
    cyril = staff_user(db_session, "interviewer", name="Cyril Moss")
    row = _first_round(application)
    first = fs.assign(db_session, row, odette)
    second = fs.assign(db_session, row, bram)
    third = fs.assign(db_session, row, cyril)
    fs.submit_feedback(
        db_session, first, odette, 4, "hire",
        "Mira explained the cache design well. Reach her at mira.q@example.test or 555-201-7788.",
    )
    fs.submit_feedback(
        db_session, second, bram, 2, "no_hire",
        "Odette and I disagree: Quillfeather was vague on testing. See https://example.test/notes.",
    )
    fs.save_draft(db_session, third, cyril, 1, "strong_no_hire", "SECRET DRAFT about Bram's question")
    db_session.commit()
    return {"application": application, "people": (odette, bram, cyril)}


def _client_for(user) -> TestClient:
    return TestClient(
        app, raise_server_exceptions=False, headers={"Authorization": f"Bearer {create_access_token(user)}"}
    )


def test_prompt_is_submitted_feedback_only_with_names_scrubbed(panel):
    application = panel["application"]
    entries = summaries.submitted_entries(application)
    assert len(entries) == 2  # the draft is not an entry
    prompt = summaries.build_prompt(application, entries)

    for leaked in ("Mira", "Quillfeather", "Odette", "Varga", "Bram", "Kettering", "Cyril",
                   "SECRET DRAFT", "mira.q@example.test", "555-201-7788", "https://example.test"):
        assert leaked not in prompt, leaked
    assert "the candidate explained the cache design" in prompt
    assert "Interviewer 1 and I disagree: the candidate was vague" in prompt
    assert "Interviewer 1" in prompt and "Interviewer 2" in prompt
    assert "Rating: 4 of 5. Recommendation: Hire." in prompt
    assert "Rating: 2 of 5. Recommendation: No hire." in prompt
    assert "Tally: 1 hire, 1 no hire, ratings from 2 to 4 of 5." in prompt
    # Never the match score.
    assert "score" not in prompt.lower() and "match" not in prompt.lower()


def test_a_colleague_without_feedback_is_not_named(db_session, panel):
    application = panel["application"]
    entries = summaries.submitted_entries(application)
    entries[0][2].notes = "Cyril Moss should run the next round."
    try:
        prompt = summaries.build_prompt(application, entries)
    finally:
        db_session.rollback()
    assert "Cyril" not in prompt and "a colleague should run the next round" in prompt


def test_summarize_routes_its_task_type_and_cleans_points():
    llm = FakeLLM()
    summary = asyncio.run(summaries.summarize("prompt", llm=llm))
    assert llm.calls[0][1]["task_type"] == "feedback_summary"
    assert summary.themes == ["Strong systems thinking - across both rounds."]
    assert summary.open_questions == ["How they handle on-call load."]
    assert summary.disagreements == []


def test_a_split_panel_never_reads_as_a_consensus(panel):
    entries = summaries.submitted_entries(panel["application"])
    split = summaries.split_note(entries)
    assert split == "The recommendations are split: 1 hire or strong hire, 1 against."
    # The model left disagreements empty; the split is carried anyway.
    summary = asyncio.run(summaries.summarize("prompt", llm=FakeLLM(), split=split))
    assert summary.disagreements == [split]
    # A model that found its own disagreement keeps it.
    found = FakeLLM(data={"themes": ["x"], "disagreements": ["Interviewer 2 doubts testing depth."]})
    assert asyncio.run(summaries.summarize("p", llm=found, split=split)).disagreements == [
        "Interviewer 2 doubts testing depth."
    ]


def test_tally_wording():
    def entry(rating, recommendation):
        return (None, None, type("F", (), {"rating": rating, "recommendation": recommendation})())

    assert summaries.tally([entry(5, "strong_hire"), entry(5, "strong_hire")]) == "2 strong hire, every rating 5 of 5."
    assert summaries.split_note([entry(5, "strong_hire"), entry(4, "hire")]) is None
    assert summaries.tally([]) == ""


def test_an_empty_summary_is_unusable():
    empty = FakeLLM(data={"themes": [], "agreements": [" "], "disagreements": [], "open_questions": []})
    with pytest.raises(ValueError):
        asyncio.run(summaries.summarize("prompt", llm=empty))


def test_route_returns_the_brief_for_a_hiring_manager(db_session, override_get_db, panel, monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(summaries, "get_llm_service", lambda: llm)
    application_id = panel["application"].id
    response = staff_client(db_session, "hiring_manager").get(
        f"/api/applications/{application_id}/feedback-summary"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["application_id"] == application_id and body["feedback_count"] == 2
    assert body["generated_at"]
    assert body["tally"] == "1 hire, 1 no hire, ratings from 2 to 4 of 5."
    assert body["disagreements"] == ["The recommendations are split: 1 hire or strong hire, 1 against."]
    assert body["agreements"] == ["Both interviewers rate communication highly."]
    assert "SECRET DRAFT" not in llm.calls[0][0]


def test_route_refuses_under_two_submissions_and_drafts_do_not_count(
    db_session, override_get_db, monkeypatch
):
    monkeypatch.setattr(summaries, "get_llm_service", lambda: FakeLLM())
    _, application = make_application(db_session)
    lone = staff_user(db_session, "interviewer", name="Lone Voice")
    drafter = staff_user(db_session, "interviewer", name="Still Drafting")
    row = _first_round(application)
    fs.submit_feedback(db_session, fs.assign(db_session, row, lone), lone, 3, "hire", "Fine.")
    fs.save_draft(db_session, fs.assign(db_session, row, drafter), drafter, 4, "hire", "Nearly done")
    db_session.commit()
    response = staff_client(db_session, "admin").get(f"/api/applications/{application.id}/feedback-summary")
    assert response.status_code == 409
    assert "at least 2" in response.json()["detail"] and "has 1" in response.json()["detail"]


def test_route_is_closed_to_interviewers_even_after_they_submit(db_session, override_get_db, panel, monkeypatch):
    monkeypatch.setattr(summaries, "get_llm_service", lambda: FakeLLM())
    _, bram, _ = panel["people"]
    url = f"/api/applications/{panel['application'].id}/feedback-summary"
    assert _client_for(bram).get(url).status_code == 403


def test_demo_can_read_it(demo_client, panel, monkeypatch):
    monkeypatch.setattr(summaries, "get_llm_service", lambda: FakeLLM())
    response = demo_client.get(f"/api/applications/{panel['application'].id}/feedback-summary")
    assert response.status_code == 200, response.text


def test_route_reports_provider_failure_as_503(admin_client, panel, monkeypatch):
    monkeypatch.setattr(
        summaries, "get_llm_service", lambda: FakeLLM(error=AllProvidersFailedError([RuntimeError("down")]))
    )
    response = admin_client.get(f"/api/applications/{panel['application'].id}/feedback-summary")
    assert response.status_code == 503
    assert "read the feedback below" in response.json()["detail"]


def test_route_404s_for_an_unknown_application(admin_client):
    assert admin_client.get("/api/applications/987654321/feedback-summary").status_code == 404
