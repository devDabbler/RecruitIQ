"""Reports and dashboard numbers (ATS Phase D).

One job, four applications, every stage timestamp fixed. Every assertion is
computed by hand from the table below and the fixed instant NOW, so nothing
here depends on the day the suite runs or on what else is in the database:
every service call is scoped to this job or to these candidates.

    app  source    history (all 2025)
    A    referral  resume Nov 1-2, HM review Nov 2-4, technical assessment since Nov 4
    B    linkedin  resume Nov 10-13, HM review since Nov 17
    C    referral  hired: resume Sep 1-2, HM review Sep 2-12, five rounds of one day
                   each Sep 12-17, offer Sep 17-18, offer accepted Sep 18 to Oct 5,
                   Hired Oct 5 (offer declined skipped)
    D    (blank)   rejected: resume Jun 1-2, HM review Jun 2 to Sep 25 (failed there),
                   everything later skipped Sep 25

Interviews: Ivy has one on A's technical assessment (no feedback yet) and one
on C's HM review (feedback submitted). Ian has none.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.models import (
    ApplicationStage,
    Candidate,
    Feedback,
    Interview,
    Job,
    JobApplication,
    User,
)
from backend.services import pipeline_service as ps
from backend.services import reports_service as rs
from backend.tests.conftest import SEED_EMAIL_DOMAIN
from backend.utils.auth import create_access_token

NOW = datetime(2025, 11, 20, 12, 0, 0)


def test_quarter_bounds_are_calendar_quarters():
    assert rs.quarter_bounds(NOW) == (datetime(2025, 10, 1), datetime(2026, 1, 1), "Q4 2025")
    assert rs.quarter_bounds(NOW, offset=-1) == (datetime(2025, 7, 1), datetime(2025, 10, 1), "Q3 2025")
    # Crossing a year boundary backwards.
    assert rs.quarter_bounds(datetime(2026, 2, 14), offset=-1) == (
        datetime(2025, 10, 1),
        datetime(2026, 1, 1),
        "Q4 2025",
    )


@pytest.mark.parametrize(
    ("kind", "key", "status", "expected"),
    [
        ("outcome", "hired", "passed", "hired"),
        ("outcome", "offer_declined", "passed", "declined"),
        ("outcome", "hired", "skipped", None),
        ("round", "hm_review", "passed", "passed"),
        ("round", "hm_review", "failed", "rejected"),
        ("round", "hm_review", "skipped", "skipped"),
        ("round", "hm_review", "in_progress", None),
        ("round", "hm_review", "pending", None),
    ],
)
def test_event_kind(kind, key, status, expected):
    assert rs.event_kind(kind, key, status) == expected


def test_scope_normalizes_candidate_ids():
    assert rs.Scope.of().candidate_ids is None
    assert rs.Scope.of(candidate_ids={"b", "a"}).candidate_ids == frozenset({"a", "b"})
    assert rs.Scope.of(candidate_ids=set()).candidate_ids == frozenset()


IDS = {name: "00000000-0000-4000-8000-0000000d000%d" % i for i, name in enumerate("ABCD", start=1)}
JOB_TITLE = "Reports Test Analyst"


def d(month: int, day: int) -> datetime:
    return datetime(2025, month, day)


_LATER_THAN_HM = (
    "technical_written",
    "technical_interview",
    "problem_solving",
    "case_study",
    "hr_screen",
    "offer",
    "offer_accepted",
    "offer_declined",
    "hired",
)

# letter -> (source, application status, {stage key: (status, started_at, completed_at)})
# Stages not listed are pending with no timestamps.
HISTORY = {
    "A": (
        "referral",
        "active",
        {
            "resume_submitted": ("passed", d(11, 1), d(11, 2)),
            "hm_review": ("passed", d(11, 2), d(11, 4)),
            "technical_written": ("in_progress", d(11, 4), None),
        },
    ),
    "B": (
        "linkedin",
        "active",
        {
            "resume_submitted": ("passed", d(11, 10), d(11, 13)),
            "hm_review": ("in_progress", d(11, 17), None),
        },
    ),
    "C": (
        "referral",
        "hired",
        {
            "resume_submitted": ("passed", d(9, 1), d(9, 2)),
            "hm_review": ("passed", d(9, 2), d(9, 12)),
            "technical_written": ("passed", d(9, 12), d(9, 13)),
            "technical_interview": ("passed", d(9, 13), d(9, 14)),
            "problem_solving": ("passed", d(9, 14), d(9, 15)),
            "case_study": ("passed", d(9, 15), d(9, 16)),
            "hr_screen": ("passed", d(9, 16), d(9, 17)),
            "offer": ("passed", d(9, 17), d(9, 18)),
            "offer_accepted": ("passed", d(9, 18), d(10, 5)),
            "offer_declined": ("skipped", None, d(10, 5)),
            "hired": ("passed", d(10, 5), d(10, 5)),
        },
    ),
    "D": (
        "",
        "rejected",
        {
            "resume_submitted": ("passed", d(6, 1), d(6, 2)),
            "hm_review": ("failed", d(6, 2), d(9, 25)),
            **{key: ("skipped", None, d(9, 25)) for key in _LATER_THAN_HM},
        },
    ),
}


@pytest.fixture(scope="module")
def timeline(db_session, seed):
    """The job, people, applications, stage rows, and interviews from the docstring.

    Committed, not flushed: a route in this module that rolls back would
    otherwise revert to the last commit and take these rows with it.
    """
    job = Job(
        title=JOB_TITLE,
        department="Analytics",
        job_overview="Exists to give the reports a fixed history.",
        required_qualifications="SQL",
        location="Remote",
        location_type="remote",
        job_type="full_time",
        experience_level="mid",
        status="open",
        skills="SQL",
        job_metadata={},
        views=0,
        applications=4,
    )
    db_session.add(job)
    db_session.flush()
    stages = {s.key: s for s in ps.ensure_job_stages(db_session, job.id)}

    applications = {}
    for letter, (source, app_status, history) in HISTORY.items():
        db_session.add(
            Candidate(
                id=IDS[letter],
                first_name="Report",
                last_name=f"Person {letter}",
                email=f"reports-{letter.lower()}@{SEED_EMAIL_DOMAIN}",
                status="active",
                source=source or None,
                created_at=d(1, 1),
                updated_at=d(1, 1),
            )
        )
        db_session.flush()
        application = JobApplication(
            job_id=job.id,
            candidate_id=IDS[letter],
            status=app_status,
            applied_at=history["resume_submitted"][1],
            updated_at=history["resume_submitted"][1],
            source=source,
        )
        db_session.add(application)
        db_session.flush()
        for key, stage in stages.items():
            status, started, completed = history.get(key, ("pending", None, None))
            db_session.add(
                ApplicationStage(
                    application_id=application.id,
                    stage_id=stage.id,
                    status=status,
                    started_at=started,
                    completed_at=completed,
                )
            )
        applications[letter] = application
    db_session.flush()

    def stage_row(letter: str, key: str) -> ApplicationStage:
        return (
            db_session.query(ApplicationStage)
            .filter(
                ApplicationStage.application_id == applications[letter].id,
                ApplicationStage.stage_id == stages[key].id,
            )
            .one()
        )

    ivy = User(
        email=f"ivy@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role="interviewer",
        name="Ivy Interviewer",
        created_at=d(1, 1),
    )
    ian = User(
        email=f"ian@{SEED_EMAIL_DOMAIN}",
        hashed_password=None,
        role="interviewer",
        name="Ian Interviewer",
        created_at=d(1, 1),
    )
    db_session.add_all([ivy, ian])
    db_session.flush()

    waiting = Interview(
        application_stage_id=stage_row("A", "technical_written").id,
        interviewer_id=ivy.id,
        assignment_source="manual",
        created_at=d(11, 4),
    )
    done = Interview(
        application_stage_id=stage_row("C", "hm_review").id,
        interviewer_id=ivy.id,
        assignment_source="manual",
        created_at=d(9, 2),
    )
    db_session.add_all([waiting, done])
    db_session.flush()
    db_session.add(
        Feedback(
            interview_id=done.id,
            rating=4,
            recommendation="hire",
            notes="Clear thinker.",
            submitted_at=d(9, 12),
        )
    )
    db_session.commit()

    return {
        "job_id": job.id,
        "applications": {letter: app.id for letter, app in applications.items()},
        "ivy": ivy,
        "ian": ian,
    }


def _scope(timeline, **kwargs) -> rs.Scope:
    return rs.Scope.of(job_id=timeline["job_id"], **kwargs)


ROUND_KEYS = [key for key, _name, kind, _desc in ps.DEFAULT_STAGES if kind == "round"]


def test_funnel_lists_every_round_in_pipeline_order(db_session, timeline):
    assert [r["key"] for r in rs.stage_funnel(db_session, _scope(timeline))] == ROUND_KEYS


def test_funnel_counts_ever_reached_and_here_now(db_session, timeline):
    rows = {r["key"]: r for r in rs.stage_funnel(db_session, _scope(timeline))}
    counts = {key: (row["ever_reached"], row["currently_here"]) for key, row in rows.items()}
    assert counts["resume_submitted"] == (4, 0)
    # D failed here, which still counts as reached. B is here now.
    assert counts["hm_review"] == (4, 1)
    assert counts["technical_written"] == (2, 1)
    assert counts["offer_accepted"] == (1, 0)
    assert rows["technical_written"]["share_of_applicants"] == 0.5
    assert rows["hm_review"]["name"] == "Hiring manager review"


def test_totals(db_session, timeline):
    assert rs.total_applications(db_session, _scope(timeline)) == 4
    assert rs.hired_applications(db_session, _scope(timeline)) == 1


def test_scope_to_visible_candidates(db_session, timeline):
    only_a = _scope(timeline, candidate_ids={IDS["A"]})
    rows = {r["key"]: r for r in rs.stage_funnel(db_session, only_a)}
    assert rows["resume_submitted"]["ever_reached"] == 1
    assert rs.total_applications(db_session, only_a) == 1
    nobody = _scope(timeline, candidate_ids=set())
    assert rs.total_applications(db_session, nobody) == 0
    assert rs.stage_funnel(db_session, nobody) == []


def test_median_time_in_stage(db_session, timeline):
    rows = {r["key"]: r for r in rs.time_in_stage(db_session, _scope(timeline))}
    # Resume submitted took 1 (A), 3 (B), 1 (C), and 1 (D) days.
    assert rows["resume_submitted"]["median_days"] == pytest.approx(1.0)
    assert rows["resume_submitted"]["completed"] == 4
    # HM review: 2 (A), 10 (C), 115 (D, Jun 2 to Sep 25). B is still there.
    assert rows["hm_review"]["median_days"] == pytest.approx(10.0)
    assert rows["hm_review"]["completed"] == 3
    assert rows["offer_accepted"]["median_days"] == pytest.approx(17.0)
    # A is still in technical assessment, so only C's day counts.
    assert rows["technical_written"]["completed"] == 1


def test_median_interpolates_between_two_values(db_session, timeline):
    # A (1 day) and B (3 days) only: percentile_cont gives the midpoint.
    scope = _scope(timeline, candidate_ids={IDS["A"], IDS["B"]})
    rows = {r["key"]: r for r in rs.time_in_stage(db_session, scope)}
    assert rows["resume_submitted"]["median_days"] == pytest.approx(2.0)
    # Nobody in this scope finished technical assessment.
    assert "technical_written" not in rows


def test_zero_length_rows_are_not_time_spent(db_session, timeline):
    # C's Hired outcome starts and ends on the same instant, and outcomes are
    # not rounds anyway; neither shows up as a 0-day median.
    keys = {r["key"] for r in rs.time_in_stage(db_session, _scope(timeline))}
    assert "hired" not in keys and "offer_declined" not in keys


def test_no_movement_uses_the_injected_now(db_session, timeline):
    rows, total = rs.no_movement(db_session, _scope(timeline), NOW)
    assert total == 1
    assert [(r["candidate_id"], r["stage_key"], r["days_waiting"]) for r in rows] == [
        (IDS["A"], "technical_written", 16)
    ]
    assert rows[0]["job_title"] == JOB_TITLE
    assert rows[0]["stage_name"] == "Technical assessment"
    # Four days later B (HM review since Nov 17) has crossed the line too,
    # and the longest wait is listed first.
    rows, total = rs.no_movement(db_session, _scope(timeline), datetime(2025, 11, 24, 12, 0))
    assert total == 2
    assert [r["candidate_id"] for r in rows] == [IDS["A"], IDS["B"]]


def test_no_movement_ignores_finished_applications(db_session, timeline):
    # C and D ended months ago but are not "waiting": they have no stage in progress.
    rows, _total = rs.no_movement(db_session, _scope(timeline), datetime(2026, 6, 1))
    assert {r["candidate_id"] for r in rows} == {IDS["A"], IDS["B"]}


def test_pending_feedback(db_session, timeline):
    rows = rs.pending_feedback(db_session, _scope(timeline), NOW)
    assert [
        (r["candidate_id"], r["stage_name"], r["interviewer_name"], r["days_pending"]) for r in rows
    ] == [(IDS["A"], "Technical assessment", "Ivy Interviewer", 16)]


def test_an_interviewer_sees_only_their_own_pending_feedback(db_session, timeline):
    assert len(rs.pending_feedback(db_session, _scope(timeline), NOW, viewer=timeline["ivy"])) == 1
    assert rs.pending_feedback(db_session, _scope(timeline), NOW, viewer=timeline["ian"]) == []


def test_a_draft_is_still_pending_feedback(db_session, timeline):
    """Track 2 Phase 4: a saved draft has not been given yet."""
    feedback = (
        db_session.query(Feedback)
        .join(Interview, Feedback.interview_id == Interview.id)
        .join(ApplicationStage, Interview.application_stage_id == ApplicationStage.id)
        .join(JobApplication, ApplicationStage.application_id == JobApplication.id)
        .filter(JobApplication.job_id == timeline["job_id"])
        .one()
    )
    feedback.status = "draft"
    db_session.commit()
    try:
        assert len(rs.pending_feedback(db_session, _scope(timeline), NOW)) == 2
    finally:
        feedback.status = "submitted"
        db_session.commit()


def test_source_mix(db_session, timeline):
    # D's blank source groups as "unknown". Ties sort by name.
    assert rs.source_mix(db_session, _scope(timeline)) == [
        {"source": "referral", "applications": 2, "hired": 1},
        {"source": "linkedin", "applications": 1, "hired": 0},
        {"source": "unknown", "applications": 1, "hired": 0},
    ]


def test_outcomes_by_quarter(db_session, timeline):
    this_quarter = rs.outcomes_between(db_session, _scope(timeline), *rs.quarter_bounds(NOW))
    last_quarter = rs.outcomes_between(db_session, _scope(timeline), *rs.quarter_bounds(NOW, offset=-1))
    # C was hired Oct 5 (Q4). D was rejected Sep 25 (Q3).
    assert (this_quarter["label"], this_quarter["hires"], this_quarter["rejections"]) == ("Q4 2025", 1, 0)
    assert this_quarter["offers_declined"] == 0
    assert (last_quarter["label"], last_quarter["hires"], last_quarter["rejections"]) == ("Q3 2025", 0, 1)


def test_activity_newest_first(db_session, timeline):
    events = rs.activity(db_session, _scope(timeline), limit=8)
    assert [(e["kind"], e["candidate_id"], e["stage_name"]) for e in events] == [
        ("passed", IDS["B"], "Resume submitted"),  # Nov 13
        ("applied", IDS["B"], None),  # Nov 10
        ("passed", IDS["A"], "Hiring manager review"),  # Nov 4
        ("passed", IDS["A"], "Resume submitted"),  # Nov 2
        ("applied", IDS["A"], None),  # Nov 1
        # Oct 5: Offer accepted passing at the same instant is folded into the hire.
        ("hired", IDS["C"], "Hired"),
        ("rejected", IDS["D"], "Hiring manager review"),  # Sep 25
        ("passed", IDS["C"], "Offer"),  # Sep 18
    ]
    assert events[0]["job_title"] == JOB_TITLE
    assert events[0]["candidate_name"] == "Report Person B"


def test_activity_leaves_out_automatic_skips(db_session, timeline):
    events = rs.activity(db_session, _scope(timeline), limit=100)
    # D's seven later rounds and C's Offer declined were skipped by the
    # system, not by a person.
    assert not [e for e in events if e["kind"] == "skipped"]


def test_dashboard_bundle(db_session, timeline):
    data = rs.dashboard(db_session, _scope(timeline), NOW)
    assert data["total_applications"] == 4
    # A is at technical assessment (round 3) and C is hired; B at HM review is not counted.
    assert data["interviewing_or_later"] == 2
    assert data["no_movement_total"] == 1
    assert [p["candidate_id"] for p in data["pending_feedback"]] == [IDS["A"]]
    assert data["generated_at"] == NOW


def test_reports_bundle(db_session, timeline):
    data = rs.reports(db_session, _scope(timeline), NOW)
    assert [q["label"] for q in data["quarters"]] == ["Q4 2025", "Q3 2025"]
    assert data["job_id"] == timeline["job_id"]
    assert len(data["funnel"]) == 9
    assert data["no_movement_total"] == 1


@pytest.fixture(scope="module")
def interviewer_client(override_get_db, timeline):
    token = create_access_token(timeline["ivy"])
    return TestClient(app, raise_server_exceptions=False, headers={"Authorization": f"Bearer {token}"})


def test_summary_for_one_job(admin_client, timeline):
    response = admin_client.get("/api/reports/summary", params={"job_id": timeline["job_id"]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_title"] == JOB_TITLE
    assert body["total_applications"] == 4
    hm = next(t for t in body["time_in_stage"] if t["key"] == "hm_review")
    assert hm["median_days"] == pytest.approx(10.0)
    assert len(body["quarters"]) == 2
    assert {s["source"] for s in body["source_mix"]} == {"referral", "linkedin", "unknown"}


def test_summary_for_an_unknown_job_is_404(admin_client):
    assert admin_client.get("/api/reports/summary", params={"job_id": 99999999}).status_code == 404


def test_the_demo_can_read_reports(demo_client):
    response = demo_client.get("/api/reports/summary")
    assert response.status_code == 200, response.text
    assert "funnel" in response.json()


def test_an_interviewer_cannot_read_reports(interviewer_client):
    response = interviewer_client.get("/api/reports/summary")
    # Phase B's interviewer gate answers before the handler, with its own sentence.
    assert response.status_code == 403


def test_anonymous_callers_cannot_read_reports(client):
    assert client.get("/api/reports/summary").status_code == 401


def test_the_dashboard_is_open_to_everyone(client, demo_client):
    for caller in (client, demo_client):
        response = caller.get("/api/reports/dashboard")
        assert response.status_code == 200, response.text
        assert {"funnel", "no_movement", "pending_feedback", "activity"} <= set(response.json())


def test_an_interviewer_dashboard_counts_only_assigned_candidates(interviewer_client):
    body = interviewer_client.get("/api/reports/dashboard").json()
    # Ivy has interviews on A and C, so only their two applications exist for her.
    assert body["total_applications"] == 2
    assert [p["candidate_id"] for p in body["pending_feedback"]] == [IDS["A"]]


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def tools(db_session, timeline):
    from backend.services.assistant_tools import build_assistant_tools

    return {t.name: t for t in build_assistant_tools(db_session)}


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("HM review", "hm review"),
        ("the hiring manager review stage", "hiring manager review"),
        ("Technical-Interview round", "technical interview"),
        ("  offer_accepted ", "offer accepted"),
    ],
)
def test_normalize_stage_text(typed, expected):
    assert rs.normalize_stage_text(typed) == expected


def test_resolve_stage(db_session, timeline):
    job_id = timeline["job_id"]
    assert rs.resolve_stage(db_session, "HM review", job_id=job_id)[0] == ["hm_review"]
    assert rs.resolve_stage(db_session, "technical", job_id=job_id)[0] == ["technical_written", "technical_interview"]
    assert rs.resolve_stage(db_session, "screening", job_id=job_id)[0] == ["hm_review"]
    keys, stages = rs.resolve_stage(db_session, "astrology", job_id=job_id)
    assert keys == [] and "Resume submitted" in stages.values()


def test_get_job_pipeline_tool(tools, timeline):
    out = _run(tools["get_job_pipeline"].run(job=JOB_TITLE))
    assert (out["job_id"], out["job_title"]) == (timeline["job_id"], JOB_TITLE)
    assert out["in_progress"] == 2
    assert out["stage_counts"] == {"Hiring manager review": 1, "Technical assessment": 1}
    assert out["outcomes"] == {"hired": 1, "rejected": 1, "declined": 0, "withdrawn": 0}
    hm = next(s for s in out["stages"] if s["stage"] == "Hiring manager review")
    assert [c["id"] for c in hm["candidates"]] == [IDS["B"]]


def test_get_job_pipeline_tool_unknown_job(tools):
    out = _run(tools["get_job_pipeline"].run(job="zzz-not-a-job-zzz"))
    assert "error" in out and isinstance(out["open_jobs"], list)


def test_find_candidates_at_stage_tool(tools):
    out = _run(tools["find_candidates_at_stage"].run(stage="technical assessment", job=JOB_TITLE))
    assert out["stages_matched"] == ["Technical assessment"]
    assert out["count"] == 1 and out["candidates"][0]["id"] == IDS["A"]

    interviewing = _run(tools["find_candidates_at_stage"].run(stage="interviewing", job=JOB_TITLE))
    assert "Technical interview" in interviewing["stages_matched"]
    assert [c["id"] for c in interviewing["candidates"]] == [IDS["A"]]


def test_find_candidates_at_an_unknown_stage(tools):
    out = _run(tools["find_candidates_at_stage"].run(stage="astrology"))
    assert "error" in out
    assert "Resume submitted" in out["stages"]
    assert "astrology" in out["note"]
