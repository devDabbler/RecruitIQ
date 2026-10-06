"""Pipeline stages and application stage history (ATS Phase A).

Runs against the real schema inside the session-wide rolled-back transaction
from conftest. The seeded application (candidate 0 on job 0) has no stage rows
until something asks for them, which is exactly the state existing production
rows are in, so these tests also cover the lazy-repair path.
"""
from __future__ import annotations

import pytest

from backend.models.models import ApplicationStage, Candidate, JobApplication, PipelineStage
from backend.services import pipeline_service as ps


@pytest.fixture
def application(db_session, seed) -> JobApplication:
    return db_session.get(JobApplication, seed["application_id"])


@pytest.fixture(autouse=True)
def _reset_application(db_session, seed):
    """Every test starts from a fresh, unstarted application.

    Commits rather than flushes: a route that hits a 409 rolls the session
    back to its last commit, which would otherwise resurrect the previous
    test's stage rows.
    """
    yield
    app = db_session.get(JobApplication, seed["application_id"])
    for row in list(app.stages):
        db_session.delete(row)
    app.status = "active"
    db_session.get(Candidate, app.candidate_id).status = "active"
    db_session.commit()
    db_session.expire(app)


def _keys_by_status(application, status):
    return [r.stage.key for r in sorted(application.stages, key=lambda r: r.stage.position) if r.status == status]


# --- models -----------------------------------------------------------------


def test_models_import_and_map():
    assert PipelineStage.__tablename__ == "pipeline_stages"
    assert ApplicationStage.__tablename__ == "application_stages"
    assert "stages" in JobApplication.__mapper__.relationships


# --- ensure functions -------------------------------------------------------


def test_ensure_job_stages_creates_the_eleven_defaults(db_session, seed):
    stages = ps.ensure_job_stages(db_session, seed["job_ids"][1])
    assert [s.key for s in stages] == [key for key, *_ in ps.DEFAULT_STAGES]
    assert [s.kind for s in stages][-2:] == ["outcome", "outcome"]
    # Idempotent: a second call returns the same rows, not duplicates.
    again = ps.ensure_job_stages(db_session, seed["job_ids"][1])
    assert [s.id for s in again] == [s.id for s in stages]


def test_ensure_application_stages_starts_at_resume_submitted(db_session, application):
    rows = ps.ensure_application_stages(db_session, application)
    assert len(rows) == len(ps.DEFAULT_STAGES)
    assert rows[0].stage.key == "resume_submitted"
    assert rows[0].status == "in_progress"
    assert rows[0].started_at is not None
    assert all(r.status == "pending" for r in rows[1:])
    assert ps.current_stage(application).stage.key == "resume_submitted"


# --- transitions ------------------------------------------------------------


def test_advance_moves_to_the_next_enabled_round(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.advance(db_session, application)
    assert _keys_by_status(application, "passed") == ["resume_submitted"]
    assert ps.current_stage(application).stage.key == "hm_review"
    assert db_session.get(Candidate, application.candidate_id).status == "screening"


def test_advance_skips_disabled_rounds(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.advance(db_session, application)  # now at hm_review
    stages = {s.key: s for s in ps.ensure_job_stages(db_session, application.job_id)}
    stages["technical_written"].enabled = False
    db_session.flush()
    try:
        ps.advance(db_session, application)
        assert ps.current_stage(application).stage.key == "technical_interview"
        assert _keys_by_status(application, "skipped") == ["technical_written"]
    finally:
        stages["technical_written"].enabled = True
        db_session.flush()


def test_advance_from_the_last_round_hires(db_session, application):
    ps.ensure_application_stages(db_session, application)
    for _ in range(9):
        ps.advance(db_session, application)
    assert application.status == "hired"
    assert ps.current_stage(application) is None
    assert "hired" in _keys_by_status(application, "passed")
    assert _keys_by_status(application, "skipped") == ["offer_declined", "withdrawn"]
    assert db_session.get(Candidate, application.candidate_id).status == "hired"
    with pytest.raises(ps.PipelineError):
        ps.advance(db_session, application)


def test_reject_fails_current_and_skips_the_rest(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.advance(db_session, application)
    ps.reject(db_session, application, note="Not enough SQL depth.")
    assert application.status == "rejected"
    assert _keys_by_status(application, "failed") == ["hm_review"]
    assert len(_keys_by_status(application, "skipped")) == 10
    failed = next(r for r in application.stages if r.status == "failed")
    assert failed.note == "Not enough SQL depth."
    assert db_session.get(Candidate, application.candidate_id).status == "rejected"


def test_skip_passes_over_the_current_round(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.skip(db_session, application)
    assert _keys_by_status(application, "skipped") == ["resume_submitted"]
    assert ps.current_stage(application).stage.key == "hm_review"


def test_skip_refused_on_the_last_round(db_session, application):
    ps.ensure_application_stages(db_session, application)
    for _ in range(8):
        ps.advance(db_session, application)
    assert ps.current_stage(application).stage.key == "offer_accepted"
    with pytest.raises(ps.PipelineError):
        ps.skip(db_session, application)
    # A refused skip leaves the application exactly where it was.
    assert ps.current_stage(application).stage.key == "offer_accepted"
    assert application.status == "active"


def test_decline_only_at_offer(db_session, application):
    ps.ensure_application_stages(db_session, application)
    with pytest.raises(ps.PipelineError):
        ps.decline(db_session, application)
    for _ in range(7):
        ps.advance(db_session, application)
    assert ps.current_stage(application).stage.key == "offer"
    ps.decline(db_session, application)
    assert application.status == "declined"
    assert "offer_declined" in _keys_by_status(application, "passed")
    assert "hired" in _keys_by_status(application, "skipped")
    assert db_session.get(Candidate, application.candidate_id).status == "withdrawn"


def test_terminal_application_refuses_everything(db_session, application):
    ps.ensure_application_stages(db_session, application)
    ps.reject(db_session, application)
    for action in (ps.advance, ps.skip, ps.reject, ps.decline):
        with pytest.raises(ps.PipelineError):
            action(db_session, application)


# --- routes -----------------------------------------------------------------


def test_get_job_pipeline_has_a_column_per_enabled_stage(client, seed):
    response = client.get(f"/api/jobs/{seed['job_id']}/pipeline")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == seed["job_id"]
    assert [s["key"] for s in body["stages"]][:2] == ["resume_submitted", "hm_review"]
    assert len(body["columns"]) == 9  # rounds only; outcomes are counts
    first = body["columns"][0]
    assert first["stage_key"] == "resume_submitted"
    assert any(a["application_id"] == seed["application_id"] for a in first["applications"])
    assert body["outcomes"] == {"hired": 0, "rejected": 0, "declined": 0, "withdrawn": 0}


def test_get_application_returns_the_timeline(client, seed):
    response = client.get(f"/api/applications/{seed['application_id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "active"
    assert body["current_stage_key"] == "resume_submitted"
    assert len(body["stages"]) == len(ps.DEFAULT_STAGES)
    assert body["stages"][0]["status"] == "in_progress"
    assert body["candidate_name"] == "Ada Lovelace"


def test_unknown_application_is_404(client):
    assert client.get("/api/applications/99999999").status_code == 404


def test_actions_require_admin(demo_client, seed):
    response = demo_client.post(f"/api/applications/{seed['application_id']}/advance", json={})
    assert response.status_code == 403


def test_advance_route_moves_the_application(admin_client, admin_user, seed):
    response = admin_client.post(
        f"/api/applications/{seed['application_id']}/advance", json={"note": "  Strong resume.  "}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_stage_key"] == "hm_review"
    assert body["stages"][0]["note"] == "Strong resume."


def test_unknown_action_is_404(admin_client, seed):
    response = admin_client.post(f"/api/applications/{seed['application_id']}/promote", json={})
    assert response.status_code == 404


def test_illegal_transition_is_409(admin_client, seed):
    response = admin_client.post(f"/api/applications/{seed['application_id']}/decline", json={})
    assert response.status_code == 409
    assert "offer" in response.json()["detail"].lower()


def test_put_pipeline_disables_a_stage(admin_client, seed):
    response = admin_client.put(
        f"/api/jobs/{seed['job_id']}/pipeline",
        json={"stages": [{"key": "case_study", "enabled": False, "name": "Case study"}]},
    )
    assert response.status_code == 200, response.text
    case_study = next(s for s in response.json()["stages"] if s["key"] == "case_study")
    assert case_study["enabled"] is False
    assert "case_study" not in [c["stage_key"] for c in response.json()["columns"]]
    # Restore so later tests see the default.
    admin_client.put(
        f"/api/jobs/{seed['job_id']}/pipeline",
        json={"stages": [{"key": "case_study", "enabled": True, "name": "Case study"}]},
    )


def test_put_pipeline_never_disables_the_first_round_or_an_outcome(admin_client, seed):
    for key, name in (("resume_submitted", "Resume submitted"), ("hired", "Hired")):
        response = admin_client.put(
            f"/api/jobs/{seed['job_id']}/pipeline",
            json={"stages": [{"key": key, "enabled": False, "name": name}]},
        )
        assert response.status_code == 409, key
        assert "cannot be turned off" in response.json()["detail"]


def test_put_pipeline_refuses_to_disable_a_stage_in_use(admin_client, seed):
    # Move the seeded application to Hiring manager review, then try to turn
    # that stage off underneath it.
    moved = admin_client.post(f"/api/applications/{seed['application_id']}/advance", json={})
    assert moved.json()["current_stage_key"] == "hm_review"
    response = admin_client.put(
        f"/api/jobs/{seed['job_id']}/pipeline",
        json={"stages": [{"key": "hm_review", "enabled": False, "name": "Hiring manager review"}]},
    )
    assert response.status_code == 409
    assert "Move them first" in response.json()["detail"]


# --- hooks in the jobs router ----------------------------------------------


def test_creating_a_job_seeds_its_stages(admin_client, db_session):
    response = admin_client.post(
        "/api/jobs/",
        json={
            "title": "Pipeline Test Engineer",
            "department": "Engineering",
            "job_overview": "Exists to test stage seeding.",
            "required_qualifications": "Python",
            "skills": ["Python"],
        },
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    assert db_session.query(PipelineStage).filter(PipelineStage.job_id == job_id).count() == len(ps.DEFAULT_STAGES)


def test_apply_starts_the_pipeline(admin_client, seed):
    response = admin_client.post(
        f"/api/jobs/{seed['job_ids'][1]}/apply",
        json={"candidate_id": seed["candidate_ids"][1], "source": "referral"},
    )
    assert response.status_code == 200, response.text
    application_id = response.json()["id"]
    detail = admin_client.get(f"/api/applications/{application_id}").json()
    assert detail["current_stage_key"] == "resume_submitted"
    assert detail["status"] == "active"


def test_candidate_applications_carry_the_current_stage(client, seed):
    response = client.get(f"/api/jobs/applications/{seed['candidate_id']}")
    assert response.status_code == 200, response.text
    row = next(a for a in response.json() if a["id"] == seed["application_id"])
    assert row["current_stage_key"] == "resume_submitted"
    assert row["current_stage"] == "Resume submitted"


def test_deleting_a_job_with_a_moved_application_removes_its_pipeline(admin_client, db_session, seed):
    created = admin_client.post(
        "/api/jobs/",
        json={
            "title": "Pipeline Delete Engineer",
            "department": "Engineering",
            "job_overview": "Exists to be deleted with stage history attached.",
            "required_qualifications": "Python",
            "skills": ["Python"],
        },
    )
    job_id = created.json()["id"]
    applied = admin_client.post(
        f"/api/jobs/{job_id}/apply",
        json={"candidate_id": seed["candidate_ids"][2], "source": "direct_application"},
    )
    application_id = applied.json()["id"]
    assert admin_client.post(f"/api/applications/{application_id}/advance", json={}).status_code == 200

    response = admin_client.delete(f"/api/jobs/{job_id}")
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(PipelineStage).filter(PipelineStage.job_id == job_id).count() == 0
    assert (
        db_session.query(ApplicationStage)
        .filter(ApplicationStage.application_id == application_id)
        .count()
        == 0
    )
