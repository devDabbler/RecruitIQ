"""Interviews, feedback, and default interviewers (ATS Phase B).

Uses `scoped_application` from conftest (its own job and application) so the
seeded application that test_pipeline relies on is never touched.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect

import pytest

from backend.models.models import (
    ApplicationStage,
    Feedback,
    Interview,
    JobApplication,
    PipelineStage,
    StageDefaultInterviewer,
    User,
)
from backend.services import feedback_service as fs
from backend.services import pipeline_service as ps
from backend.services.access_service import can_see_score, visible_candidate_ids


def test_models_import_and_map():
    assert Interview.__tablename__ == "interviews"
    assert Feedback.__tablename__ == "feedback"
    assert StageDefaultInterviewer.__tablename__ == "stage_default_interviewers"
    assert "interviews" in ApplicationStage.__mapper__.relationships
    assert "default_interviewers" in PipelineStage.__mapper__.relationships
    assert "name" in User.__table__.columns
    assert "timezone" in User.__table__.columns


@pytest.fixture(autouse=True)
def _fresh(db_session, scoped_application):
    """Every test starts with the scoped application at stage 1, nobody assigned.

    Commits rather than flushes: a route that hits a 409 rolls the session
    back to its last commit (the Phase A lesson).
    """
    yield
    db_session.rollback()
    application = db_session.get(JobApplication, scoped_application["application_id"])
    for row in list(application.stages):
        db_session.delete(row)  # interviews and feedback go with it (cascade)
    for stage in ps.ensure_job_stages(db_session, application.job_id):
        stage.default_interviewers.clear()
        stage.enabled = True
    application.status = "active"
    db_session.flush()
    db_session.expire(application)
    ps.start_application(db_session, db_session.get(JobApplication, scoped_application["application_id"]))
    db_session.commit()


@pytest.fixture
def application(db_session, scoped_application) -> JobApplication:
    return db_session.get(JobApplication, scoped_application["application_id"])


def _row(application, key):
    return next(r for r in application.stages if r.stage.key == key)


# --- service ----------------------------------------------------------------


def test_assign_is_idempotent_and_refuses_outcomes(db_session, application, staff_users):
    interviewer = staff_users["interviewer"]
    first = fs.assign(db_session, _row(application, "resume_submitted"), interviewer)
    again = fs.assign(db_session, _row(application, "resume_submitted"), interviewer)
    assert first.id == again.id
    assert first.assignment_source == "manual"
    with pytest.raises(fs.FeedbackError):
        fs.assign(db_session, _row(application, "hired"), interviewer)


def test_assign_refuses_people_outside_the_team(db_session, application):
    with pytest.raises(fs.FeedbackError) as caught:
        fs.assign(db_session, _row(application, "hm_review"), None)
    assert caught.value.status_code == 422


def test_default_interviewers_are_assigned_when_the_stage_starts(db_session, application, staff_users):
    stages = {s.key: s for s in ps.ensure_job_stages(db_session, application.job_id)}
    fs.set_default_interviewers(db_session, stages["hm_review"], [staff_users["interviewer"].id])
    ps.advance(db_session, application)
    row = _row(application, "hm_review")
    assert [(i.interviewer_id, i.assignment_source) for i in row.interviews] == [
        (staff_users["interviewer"].id, "default")
    ]


def test_feedback_is_for_the_assignee_once(db_session, application, staff_users):
    interviewer, colleague = staff_users["interviewer"], staff_users["hiring_team"]
    interview = fs.assign(db_session, _row(application, "resume_submitted"), interviewer)
    with pytest.raises(fs.FeedbackError) as not_theirs:
        fs.submit_feedback(db_session, interview, colleague, 4, "hire", "")
    assert not_theirs.value.status_code == 403
    fs.submit_feedback(db_session, interview, interviewer, 4, "hire", "  Clear thinker.  ")
    assert interview.feedback.notes == "Clear thinker."
    with pytest.raises(fs.FeedbackError) as twice:
        fs.submit_feedback(db_session, interview, interviewer, 5, "strong_hire", "")
    assert twice.value.status_code == 409


def test_feedback_waits_for_the_stage_to_start(db_session, application, staff_users):
    interview = fs.assign(db_session, _row(application, "technical_interview"), staff_users["interviewer"])
    with pytest.raises(fs.FeedbackError):
        fs.submit_feedback(db_session, interview, staff_users["interviewer"], 3, "hire", "")


def test_unassign_keeps_submitted_feedback_on_record(db_session, application, staff_users):
    interview = fs.assign(db_session, _row(application, "resume_submitted"), staff_users["interviewer"])
    fs.submit_feedback(db_session, interview, staff_users["interviewer"], 2, "no_hire", "")
    with pytest.raises(fs.FeedbackError):
        fs.unassign(db_session, interview)


def test_pending_feedback_lists_started_stages_only(db_session, application, staff_users):
    now = fs.assign(db_session, _row(application, "resume_submitted"), staff_users["interviewer"])
    later = fs.assign(db_session, _row(application, "case_study"), staff_users["interviewer"])
    pending = fs.pending_feedback(db_session, staff_users["interviewer"].id)
    assert now in pending and later not in pending
    assert fs.interview_state(now) == "waiting"
    assert fs.interview_state(later) == "upcoming"


def test_visibility_rules(db_session, application, staff_users, seed):
    interviewer = staff_users["interviewer"]
    assert visible_candidate_ids(db_session, staff_users["hiring_team"]) is None
    assert visible_candidate_ids(db_session, None) is None
    assert application.candidate_id not in visible_candidate_ids(db_session, interviewer)

    interview = fs.assign(db_session, _row(application, "resume_submitted"), interviewer)
    assert visible_candidate_ids(db_session, interviewer) == {application.candidate_id}
    assert not can_see_score(db_session, interviewer, application.candidate_id)
    assert can_see_score(db_session, staff_users["hiring_team"], application.candidate_id)
    assert can_see_score(db_session, None, application.candidate_id)

    fs.submit_feedback(db_session, interview, interviewer, 4, "hire", "")
    assert can_see_score(db_session, interviewer, application.candidate_id)


def test_display_name_never_falls_back_to_an_email(db_session, staff_users):
    nameless = User(email="private.person@example.com", role="admin")
    assert fs.display_name(nameless) == "Admin"
    assert "@" not in fs.display_name(nameless)
    assert fs.display_name(staff_users["interviewer"]) == "Test Interviewer"
    assert fs.display_name(None) == "Former team member"


# --- routes -----------------------------------------------------------------


def _assign(client, application_id, stage_key, user):
    return client.post(
        f"/api/applications/{application_id}/interviews",
        json={"stage_key": stage_key, "interviewer_id": user.id},
    )


def test_hiring_team_can_assign_and_the_interviewer_can_give_feedback(
    hiring_team_client, interviewer_client, scoped_application, staff_users
):
    app_id = scoped_application["application_id"]
    assigned = _assign(hiring_team_client, app_id, "resume_submitted", staff_users["interviewer"])
    assert assigned.status_code == 201, assigned.text
    interview = assigned.json()
    assert interview["state"] == "waiting"
    assert interview["interviewer_name"] == "Test Interviewer"

    given = interviewer_client.post(
        f"/api/interviews/{interview['id']}/feedback",
        json={"rating": 4, "recommendation": "hire", "notes": "Solid fundamentals."},
    )
    assert given.status_code == 200, given.text
    assert given.json()["feedback"]["rating"] == 4

    again = interviewer_client.post(
        f"/api/interviews/{interview['id']}/feedback",
        json={"rating": 5, "recommendation": "strong_hire"},
    )
    assert again.status_code == 409


def test_assignment_needs_pipeline_permission(interviewer_client, demo_client, scoped_application, staff_users):
    app_id = scoped_application["application_id"]
    assert _assign(interviewer_client, app_id, "hm_review", staff_users["interviewer"]).status_code == 403
    assert _assign(demo_client, app_id, "hm_review", staff_users["interviewer"]).status_code == 403


def test_feedback_validation(hiring_team_client, interviewer_client, scoped_application, staff_users):
    interview = _assign(
        hiring_team_client, scoped_application["application_id"], "resume_submitted", staff_users["interviewer"]
    ).json()
    for bad in ({"rating": 0, "recommendation": "hire"}, {"rating": 3, "recommendation": "maybe"}):
        response = interviewer_client.post(f"/api/interviews/{interview['id']}/feedback", json=bad)
        assert response.status_code == 422


def test_someone_elses_interview_is_403(hiring_team_client, scoped_application, staff_users):
    interview = _assign(
        hiring_team_client, scoped_application["application_id"], "resume_submitted", staff_users["interviewer"]
    ).json()
    response = hiring_team_client.post(
        f"/api/interviews/{interview['id']}/feedback", json={"rating": 3, "recommendation": "hire"}
    )
    assert response.status_code == 403


def test_colleagues_feedback_is_hidden_until_you_give_yours(
    hiring_team_client, interviewer_client, scoped_application, staff_users
):
    app_id = scoped_application["application_id"]
    theirs = _assign(hiring_team_client, app_id, "resume_submitted", staff_users["hiring_team"]).json()
    mine = _assign(hiring_team_client, app_id, "resume_submitted", staff_users["interviewer"]).json()
    hiring_team_client.post(
        f"/api/interviews/{theirs['id']}/feedback", json={"rating": 2, "recommendation": "no_hire"}
    )

    before = {i["id"]: i for i in interviewer_client.get(f"/api/applications/{app_id}/interviews").json()}
    assert before[theirs["id"]]["feedback"] is None
    assert before[theirs["id"]]["feedback_hidden"] is True

    interviewer_client.post(f"/api/interviews/{mine['id']}/feedback", json={"rating": 4, "recommendation": "hire"})
    after = {i["id"]: i for i in interviewer_client.get(f"/api/applications/{app_id}/interviews").json()}
    assert after[theirs["id"]]["feedback"]["recommendation"] == "no_hire"


def test_unassign_route(hiring_team_client, scoped_application, staff_users):
    interview = _assign(
        hiring_team_client, scoped_application["application_id"], "hm_review", staff_users["interviewer"]
    ).json()
    assert hiring_team_client.delete(f"/api/interviews/{interview['id']}").status_code == 200
    assert hiring_team_client.delete(f"/api/interviews/{interview['id']}").status_code == 404


def test_default_interviewer_routes(
    hiring_manager_client, hiring_team_client, admin_client, scoped_application, staff_users
):
    job_id = scoped_application["job_id"]
    path = f"/api/jobs/{job_id}/stages/hm_review/default-interviewers"
    body = {"user_ids": [staff_users["interviewer"].id]}
    assert hiring_team_client.put(path, json=body).status_code == 403
    saved = hiring_manager_client.put(path, json=body)
    assert saved.status_code == 200, saved.text
    hm_review = next(s for s in saved.json()["stages"] if s["stage_key"] == "hm_review")
    assert [u["id"] for u in hm_review["users"]] == [staff_users["interviewer"].id]

    moved = admin_client.post(f"/api/applications/{scoped_application['application_id']}/advance", json={})
    assert moved.status_code == 200
    interviews = admin_client.get(f"/api/applications/{scoped_application['application_id']}/interviews").json()
    assert [(i["stage_key"], i["assignment_source"]) for i in interviews] == [("hm_review", "default")]


def test_interview_lists(hiring_team_client, interviewer_client, demo_client, scoped_application, staff_users):
    _assign(hiring_team_client, scoped_application["application_id"], "resume_submitted", staff_users["interviewer"])
    mine = interviewer_client.get("/api/interviews", params={"scope": "mine"}).json()["items"]
    assert [i["candidate_id"] for i in mine] == [scoped_application["candidate_id"]]
    assert mine[0]["score_visible"] is False
    assert interviewer_client.get("/api/interviews", params={"scope": "all"}).status_code == 403
    pending = hiring_team_client.get("/api/interviews", params={"scope": "pending"}).json()["items"]
    assert any(i["candidate_id"] == scoped_application["candidate_id"] for i in pending)
    assert demo_client.get("/api/interviews", params={"scope": "all"}).status_code == 200
    assert demo_client.get("/api/interviews", params={"scope": "mine"}).json()["items"] == []


# --- feedback never reaches the scorer ----------------------------------------

# Every module on the path from a candidate to a match score or a search
# ranking. If one of them ever mentions feedback, the transparency page's
# promise needs re-reading.
SCORING_MODULES = (
    "backend.services.matching_integrator",
    "backend.services.matching_enhancer",
    "backend.services.enhanced_matching_integrator",
    "backend.services.vector_search_service",
    "backend.services.search_relevance",
    "backend.services.agent_framework.agents.candidate_matching_agent",
)


@pytest.mark.parametrize("module_name", SCORING_MODULES)
def test_scoring_code_never_reads_feedback(module_name):
    source = inspect.getsource(importlib.import_module(module_name)).lower()
    assert "feedback" not in source, f"{module_name} mentions feedback"


def test_transparency_publishes_what_feedback_is_for(demo_client):
    policy = demo_client.get("/api/transparency/policy").json()["feedback_policy"]
    assert policy["used_for"] == fs.FEEDBACK_USED_FOR
    assert any("match score" in line for line in policy["never_used_for"])


# --- assistant -------------------------------------------------------------


def test_assistant_lists_pending_feedback(db_session, application, staff_users):
    from backend.services.assistant_tools import build_assistant_tools

    fs.assign(db_session, _row(application, "resume_submitted"), staff_users["interviewer"])
    db_session.flush()
    tools = {t.name: t for t in build_assistant_tools(db_session)}
    result = asyncio.run(tools["list_pending_feedback"].run())
    assert result["pending_count"] >= 1
    mine = [p for p in result["pending"] if p["candidate_id"] == application.candidate_id]
    assert mine and mine[0]["interviewer"] == "Test Interviewer"
    assert mine[0]["stage"] == "Resume submitted"
    assert "@" not in str(result)  # names only, never addresses
