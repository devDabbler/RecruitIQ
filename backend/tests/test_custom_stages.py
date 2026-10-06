"""Custom stages, reordering, and the transitions that must survive them (ATS Phase E)."""
from __future__ import annotations

import pytest

from backend.models.models import Candidate
from backend.services import pipeline_service as ps
from backend.tests.phase_e_helpers import make_application, staff_client


def _rows(application):
    return {r.stage.key: r for r in application.stages}


# --- transitions never re-open a decided round -------------------------------


def test_advance_does_not_reopen_a_decided_round(db_session):
    _, application = make_application(db_session)
    ps.advance(db_session, application)  # hm_review
    ps.advance(db_session, application)  # technical_written
    # A round ahead of the current one that already happened, which is what a
    # reorder can produce.
    _rows(application)["technical_interview"].status = ps.PASSED
    db_session.flush()

    ps.advance(db_session, application)

    assert ps.current_stage(application).stage.key == "problem_solving"
    assert _rows(application)["technical_interview"].status == ps.PASSED


def test_skip_refused_when_only_decided_rounds_remain(db_session):
    _, application = make_application(db_session)
    for _ in range(7):
        ps.advance(db_session, application)
    assert ps.current_stage(application).stage.key == "offer"
    _rows(application)["offer_accepted"].status = ps.PASSED
    db_session.flush()

    with pytest.raises(ps.PipelineError):
        ps.skip(db_session, application)
    assert ps.current_stage(application).stage.key == "offer"

    ps.advance(db_session, application)
    assert application.status == "hired"


# --- adding stages -------------------------------------------------------------


def _keys(db_session, job_id):
    return [s.key for s in ps.ensure_job_stages(db_session, job_id)]


def test_add_stage_defaults_to_just_before_the_offer(db_session):
    job, _ = make_application(db_session)
    stage = ps.add_custom_stage(db_session, job.id, "Portfolio review", "Walk us through past work.")
    keys = _keys(db_session, job.id)
    assert stage.key == "custom_portfolio_review"
    assert keys.index("custom_portfolio_review") == keys.index("offer") - 1
    assert keys[0] == "resume_submitted"
    assert keys[-3:] == ["offer_declined", "hired", "withdrawn"]
    assert [s.position for s in ps.ensure_job_stages(db_session, job.id)] == list(range(1, len(ps.DEFAULT_STAGES) + 2))
    assert ps.is_custom(stage) and ps.is_movable(stage)


def test_add_stage_after_a_given_round_and_keys_stay_unique(db_session):
    job, _ = make_application(db_session)
    first = ps.add_custom_stage(db_session, job.id, "Pair programming", after_key="resume_submitted")
    second = ps.add_custom_stage(db_session, job.id, "Pair programming", after_key="hm_review")
    keys = _keys(db_session, job.id)
    assert keys[:4] == ["resume_submitted", first.key, "hm_review", second.key]
    assert second.key == "custom_pair_programming_2"


def test_add_stage_refused_after_the_offer_or_without_a_name(db_session):
    job, _ = make_application(db_session)
    with pytest.raises(ps.PipelineError):
        ps.add_custom_stage(db_session, job.id, "Too late", after_key="offer")
    with pytest.raises(ps.PipelineError):
        ps.add_custom_stage(db_session, job.id, "   ")


def test_added_stage_count_is_capped(db_session):
    job, _ = make_application(db_session)
    for n in range(ps.MAX_CUSTOM_STAGES):
        ps.add_custom_stage(db_session, job.id, f"Extra {n}")
    with pytest.raises(ps.PipelineError):
        ps.add_custom_stage(db_session, job.id, "One too many")


def test_adding_mid_flight_skips_it_for_candidates_already_past_it(db_session):
    job, ahead = make_application(db_session)
    _, behind = make_application(db_session, job=job, first_name="Tobi")  # still at Resume submitted
    for _ in range(3):
        ps.advance(db_session, ahead)  # now at technical_interview

    stage = ps.add_custom_stage(db_session, job.id, "Culture conversation", after_key="hm_review")

    db_session.expire_all()
    ahead_rows = _rows(ahead)
    behind_rows = _rows(behind)
    assert ahead_rows[stage.key].status == ps.SKIPPED
    assert ahead_rows[stage.key].note == ps.LATE_STAGE_NOTE
    assert behind_rows[stage.key].status == ps.PENDING

    ps.advance(db_session, behind)  # hm_review
    ps.advance(db_session, behind)  # the custom stage
    assert ps.current_stage(behind).stage.key == stage.key
    assert db_session.get(Candidate, behind.candidate_id).status == "interviewing"


# --- reordering ----------------------------------------------------------------


def test_reorder_moves_interview_stages(db_session):
    job, _ = make_application(db_session)
    order = ["case_study", "hm_review", "technical_written", "technical_interview", "problem_solving", "hr_screen"]
    ps.reorder_stages(db_session, job.id, order)
    keys = _keys(db_session, job.id)
    assert keys == ["resume_submitted", *order, "offer", "offer_accepted", "offer_declined", "hired", "withdrawn"]


def test_reorder_refuses_pinned_or_partial_lists(db_session):
    job, _ = make_application(db_session)
    with pytest.raises(ps.PipelineError):
        ps.reorder_stages(db_session, job.id, ["hm_review", "technical_written"])
    with pytest.raises(ps.PipelineError):
        ps.reorder_stages(
            db_session,
            job.id,
            ["offer", "hm_review", "technical_written", "technical_interview", "problem_solving", "case_study", "hr_screen"],
        )


def test_reorder_closes_rounds_left_behind(db_session):
    job, application = make_application(db_session)
    for _ in range(3):
        ps.advance(db_session, application)  # technical_interview
    ps.reorder_stages(
        db_session,
        job.id,
        ["hm_review", "case_study", "technical_written", "technical_interview", "problem_solving", "hr_screen"],
    )
    rows = _rows(application)
    assert rows["case_study"].status == ps.SKIPPED
    assert rows["case_study"].note == ps.MOVED_STAGE_NOTE
    assert ps.current_stage(application).stage.key == "technical_interview"
    ps.advance(db_session, application)
    assert ps.current_stage(application).stage.key == "problem_solving"


# --- removing ------------------------------------------------------------------


def test_remove_custom_stage_compacts_positions(db_session):
    job, application = make_application(db_session)
    stage = ps.add_custom_stage(db_session, job.id, "Take-home review")
    ps.remove_custom_stage(db_session, job.id, stage.key)
    stages = ps.ensure_job_stages(db_session, job.id)
    assert stage.key not in [s.key for s in stages]
    assert [s.position for s in stages] == list(range(1, len(ps.DEFAULT_STAGES) + 1))
    db_session.expire_all()
    assert len(application.stages) == len(ps.DEFAULT_STAGES)


def test_remove_refuses_default_and_used_stages(db_session):
    job, application = make_application(db_session)
    with pytest.raises(ps.PipelineError, match="Turn it off"):
        ps.remove_custom_stage(db_session, job.id, "case_study")
    stage = ps.add_custom_stage(db_session, job.id, "Intro call", after_key="resume_submitted")
    ps.advance(db_session, application)  # now in progress at the custom stage
    with pytest.raises(ps.PipelineError, match="history"):
        ps.remove_custom_stage(db_session, job.id, stage.key)


# --- the PUT route -------------------------------------------------------------


def test_put_adds_a_custom_stage(admin_client, db_session):
    job, _ = make_application(db_session)
    response = admin_client.put(
        f"/api/jobs/{job.id}/pipeline",
        json={"add": [{"name": "Portfolio review", "description": "Walk us through your work."}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    added = next(s for s in body["stages"] if s["key"] == "custom_portfolio_review")
    assert added["custom"] is True and added["movable"] is True
    assert "custom_portfolio_review" in [c["stage_key"] for c in body["columns"]]
    first = next(s for s in body["stages"] if s["key"] == "resume_submitted")
    assert first["movable"] is False and first["custom"] is False


def test_put_reorders_columns(admin_client, db_session):
    job, _ = make_application(db_session)
    order = ["hr_screen", "hm_review", "technical_written", "technical_interview", "problem_solving", "case_study"]
    response = admin_client.put(f"/api/jobs/{job.id}/pipeline", json={"order": order})
    assert response.status_code == 200, response.text
    columns = [c["stage_key"] for c in response.json()["columns"]]
    assert columns == ["resume_submitted", *order, "offer", "offer_accepted"]


def test_put_rolls_back_the_whole_request_on_refusal(admin_client, db_session):
    job, _ = make_application(db_session)
    # A valid rename, then an invalid order: the rename must not survive.
    response = admin_client.put(
        f"/api/jobs/{job.id}/pipeline",
        json={
            "stages": [{"key": "case_study", "enabled": True, "name": "Renamed case study"}],
            "order": ["hm_review"],
        },
    )
    assert response.status_code == 409
    assert "exactly once" in response.json()["detail"]
    board = admin_client.get(f"/api/jobs/{job.id}/pipeline").json()
    case_study = next(s for s in board["stages"] if s["key"] == "case_study")
    assert case_study["name"] == "Case study"

    refused = admin_client.put(f"/api/jobs/{job.id}/pipeline", json={"remove": ["case_study"]})
    assert refused.status_code == 409 and "Turn it off" in refused.json()["detail"]


def test_put_pipeline_permissions(demo_client, db_session, override_get_db):
    job, _ = make_application(db_session)
    body = {"stages": [{"key": "case_study", "enabled": False, "name": "Case study"}]}
    assert demo_client.put(f"/api/jobs/{job.id}/pipeline", json=body).status_code == 403
    assert staff_client(db_session, "hiring_team").put(f"/api/jobs/{job.id}/pipeline", json=body).status_code == 403
    assert staff_client(db_session, "interviewer").put(f"/api/jobs/{job.id}/pipeline", json=body).status_code == 403
    assert staff_client(db_session, "hiring_manager").put(f"/api/jobs/{job.id}/pipeline", json=body).status_code == 200
