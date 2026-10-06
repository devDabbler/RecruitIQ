"""Track 2 Phase 1: structured job requirements and the score caps.

The rules under test:

* one missing must-have caps the score at 70, two or more at 50;
* a partial skill match counts as present;
* recorded years short of the minimum lower seniority, and 2+ years short
  counts as one missing must-have;
* a degree below the minimum counts as one missing must-have, an unknown
  degree never does;
* nice-to-haves add a bounded bonus to the skill score;
* the trace and the explanation say which cap fired and why;
* caps flag, they never drop anyone from the trace.

Jobs with no requirements scoring exactly as before is
test_score_baseline.py.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from backend.models.models import Candidate, CandidateSkill, Job
from backend.services.job_requirements import (
    CandidateProfile,
    JobRequirements,
    highest_education,
    normalize_degree,
    parse_requirements,
    years_of_experience,
)
from backend.services.matching_integrator import MatchingIntegrator


class SameVector:
    """Every title embeds identically, so role fit is maximal and the base
    score sits well above both caps."""

    is_degraded = False

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


def _job(**requirements) -> Job:
    job = Job(
        title="Data Engineer",
        job_overview="Own the pipelines.",
        required_qualifications="Python and SQL",
        skills="Python,SQL,Airflow",
        status="open",
    )
    job.requirements = requirements or None
    return job


def _candidate(skills=("Python", "SQL", "Airflow", "Kubernetes"), position="Data Engineer") -> Candidate:
    candidate = Candidate(
        id="req-test-candidate",
        first_name="Test",
        last_name="Person",
        current_position=position,
        created_at=datetime(2026, 1, 1),
    )
    candidate.skills = [CandidateSkill(skill_name=s) for s in skills]
    return candidate


@pytest.fixture
def integrator():
    return MatchingIntegrator(embedding_model=SameVector())


# --- validation ---------------------------------------------------------------


def test_requirements_validation_cleans_and_limits():
    req = JobRequirements(must_have_skills=["  Python ", "python", "", "SQL"], nice_to_have_skills="dbt, Spark")
    assert req.must_have_skills == ["Python", "SQL"]
    assert req.nice_to_have_skills == ["dbt", "Spark"]

    with pytest.raises(ValidationError):
        JobRequirements(must_have_skills=[f"skill {i}" for i in range(21)])
    with pytest.raises(ValidationError):
        JobRequirements(must_have_skills=["x" * 61])
    with pytest.raises(ValidationError):
        JobRequirements(min_years=8, max_years=3)
    with pytest.raises(ValidationError):
        JobRequirements(must_have_skills=["Python"], nice_to_have_skills=["python"])
    with pytest.raises(ValidationError):
        JobRequirements(min_education="associate")


def test_empty_requirements_are_no_requirements():
    assert parse_requirements(None) is None
    assert parse_requirements({}) is None
    assert parse_requirements({"must_have_skills": [], "min_education": "none"}) is None
    # A hand-edited row that no longer validates must not break ranking.
    assert parse_requirements({"min_years": "lots"}) is None


# --- education normalizer -----------------------------------------------------


@pytest.mark.parametrize(
    "degree, level",
    [
        ("B.Tech", "bachelor"),
        ("BSc Computer Science", "bachelor"),
        ("Bachelor of Arts", "bachelor"),
        ("BA", "bachelor"),
        ("Bachelor's in Economics", "bachelor"),
        ("MSc", "master"),
        ("MBA", "master"),
        ("M.S. in Statistics", "master"),
        ("Master of Engineering", "master"),
        ("PhD", "phd"),
        ("Ph.D. Physics", "phd"),
        ("DPhil", "phd"),
        ("Doctor of Philosophy", "phd"),
        ("Associate of Science", "none"),
        ("High School Diploma", "none"),
        ("Certificate in Project Management", None),
        ("Doctor of Medicine", None),
        ("", None),
        (None, None),
    ],
)
def test_degree_normalizer(degree, level):
    assert normalize_degree(degree) == level


def test_highest_education_ignores_unknown():
    assert highest_education(["BSc", "MBA", "Some bootcamp"]) == "master"
    assert highest_education(["Some bootcamp"]) is None
    assert highest_education([]) is None


# --- years ------------------------------------------------------------------


def test_years_merge_overlaps_and_treat_open_end_as_current():
    today = date(2026, 1, 1)
    spans = [
        (date(2016, 1, 1), date(2020, 1, 1)),  # 4 years
        (date(2019, 1, 1), date(2021, 1, 1)),  # overlaps by one, adds one
        (date(2023, 1, 1), None),  # current: 3 years
        (None, date(2010, 1, 1)),  # undated start: skipped
    ]
    assert years_of_experience(spans, today=today) == pytest.approx(8.0, abs=0.05)
    assert years_of_experience([(None, None)], today=today) is None
    assert years_of_experience([], today=today) is None


# --- caps ---------------------------------------------------------------------


def test_one_missing_must_have_caps_at_70(integrator):
    open_score = integrator.score_pair(_job(), _candidate())["match_score"]
    assert open_score > 70  # otherwise the cap would prove nothing

    trace = integrator.score_pair(_job(must_have_skills=["Python", "Rust"]), _candidate())
    cap = trace["requirement_cap"]
    assert trace["must_have"]["missing"] == ["Rust"]
    assert cap["missing_count"] == 1 and cap["limit"] == 70 and cap["applied"]
    assert trace["match_score"] == 70
    assert "Missing must-have skills: Rust" in trace["match_explanation"]
    assert "Score capped at 70 because one requirement is missing" in trace["match_explanation"]


def test_two_missing_must_haves_cap_at_50(integrator):
    trace = integrator.score_pair(_job(must_have_skills=["Rust", "Go", "Python"]), _candidate())
    assert trace["requirement_cap"]["missing_count"] == 2
    assert trace["match_score"] == 50
    assert "capped at 50 because 2 requirements are missing" in trace["match_explanation"]


def test_cap_only_lowers_a_score(integrator):
    """A weak candidate already under the cap keeps their own score; the
    cap is a ceiling, not a target."""
    weak = _candidate(skills=("Excel",), position="Sales Manager")
    trace = integrator.score_pair(_job(must_have_skills=["Rust"]), weak)
    assert trace["match_score"] < 70
    assert trace["requirement_cap"]["limit"] == 70
    assert trace["requirement_cap"]["applied"] is False
    assert "capped" not in trace["match_explanation"]
    assert "Missing must-have skills: Rust" in trace["match_explanation"]


def test_partial_match_counts_as_present(integrator):
    # "Airflow 2" is within three characters of "Airflow": the overlap
    # matcher calls that partial, and a partial must-have is present.
    trace = integrator.score_pair(
        _job(must_have_skills=["Airflow 2"]), _candidate(skills=("Python", "SQL", "Airflow"))
    )
    assert trace["must_have"]["missing"] == []
    assert trace["must_have"]["present"] == ["Airflow 2"]
    assert trace["requirement_cap"]["limit"] is None


def test_all_must_haves_present_is_not_capped(integrator):
    trace = integrator.score_pair(_job(must_have_skills=["Python", "Kubernetes"]), _candidate())
    assert trace["requirement_cap"]["missing_count"] == 0
    assert "Has all 2 must-have skills" in trace["match_explanation"]


def test_must_have_counts_in_the_skill_overlap(integrator):
    trace = integrator.score_pair(_job(must_have_skills=["Kubernetes"]), _candidate())
    assert "Kubernetes" in trace["job_skills"]
    assert "Kubernetes" in trace["skills"]["exact"]


# --- years rule ---------------------------------------------------------------


def test_years_short_lowers_seniority_and_two_short_counts_as_missing(integrator):
    job = _job(min_years=6)
    base = integrator.score_pair(_job(), _candidate())

    one_short = integrator.score_pair(job, _candidate(), CandidateProfile(years=5.0))
    assert one_short["years"]["short_by"] == 1.0
    assert one_short["experience_match_score"] == pytest.approx(base["experience_match_score"] - 10)
    assert one_short["requirement_cap"]["missing_count"] == 0

    three_short = integrator.score_pair(job, _candidate(), CandidateProfile(years=3.0))
    assert three_short["years"]["counts_as_missing"]
    assert three_short["requirement_cap"]["missing"] == ["at least 6 years of experience"]
    assert three_short["match_score"] <= 70
    assert "About 3 years of recorded experience against a minimum of 6" in three_short["match_explanation"]


def test_years_over_the_range_lowers_seniority_without_a_cap(integrator):
    base = integrator.score_pair(_job(), _candidate())
    trace = integrator.score_pair(_job(max_years=4), _candidate(), CandidateProfile(years=10.0))
    assert trace["years"]["over_by"] == 6.0
    assert trace["experience_match_score"] == pytest.approx(max(base["experience_match_score"] - 20, 0))
    assert trace["requirement_cap"]["missing_count"] == 0


def test_unknown_years_change_nothing(integrator):
    base = integrator.score_pair(_job(), _candidate())
    trace = integrator.score_pair(_job(min_years=10), _candidate(), CandidateProfile(years=None))
    assert trace["match_score"] == base["match_score"]
    assert trace["years"]["candidate_years"] is None
    assert trace["requirement_cap"]["missing_count"] == 0


# --- education rule -----------------------------------------------------------


def test_degree_below_minimum_counts_as_missing(integrator):
    trace = integrator.score_pair(_job(min_education="master"), _candidate(), CandidateProfile(degrees=["BSc"]))
    assert trace["education"]["meets"] is False
    assert trace["requirement_cap"]["missing"] == ["a master's degree"]
    assert trace["match_score"] == 70
    assert "below the master's degree asked for" in trace["match_explanation"]


def test_unknown_degree_is_never_a_cap(integrator):
    base = integrator.score_pair(_job(), _candidate())
    for profile in (CandidateProfile(degrees=["Bootcamp certificate"]), CandidateProfile(), None):
        trace = integrator.score_pair(_job(min_education="phd"), _candidate(), profile)
        assert trace["education"]["meets"] is None
        assert trace["requirement_cap"]["missing_count"] == 0
        assert trace["match_score"] == base["match_score"]


def test_degree_at_or_above_minimum_meets(integrator):
    trace = integrator.score_pair(_job(min_education="bachelor"), _candidate(), CandidateProfile(degrees=["PhD"]))
    assert trace["education"]["meets"] is True


# --- nice-to-have -------------------------------------------------------------


def test_nice_to_haves_add_a_bounded_bonus():
    integrator = MatchingIntegrator(embedding_model=None)
    candidate = _candidate(skills=("Python", "dbt"))
    base = integrator.score_pair(_job(), candidate)
    trace = integrator.score_pair(_job(nice_to_have_skills=["dbt", "Spark"]), candidate)
    nice = trace["nice_to_have"]
    assert nice["exact"] == ["dbt"] and nice["missing"] == ["Spark"]
    assert nice["bonus"] == pytest.approx(5.0)
    assert trace["skill_match_score"] == pytest.approx(base["skill_match_score"] + 5.0)
    assert trace["match_score"] > base["match_score"]
    assert "Has 1 of 2 nice-to-have skills" in trace["match_explanation"]


def test_unscored_fields_still_do_not_move_a_requirement_score(integrator):
    """Requirements must not open a side door for name, location, etc."""
    job = _job(must_have_skills=["Rust"], min_years=5, min_education="master")
    profile = CandidateProfile(years=2.0, degrees=["BSc"])
    a = _candidate()
    b = _candidate()
    b.first_name, b.last_name, b.location, b.headline = "Someone", "Else", "Lagos", "Parent of three"
    b.current_company, b.source, b.status, b.notes = "Other Co", "agency", "rejected", "note"
    assert integrator.score_pair(job, a, profile)["match_score"] == integrator.score_pair(job, b, profile)["match_score"]


def test_seed_requirements_are_valid_and_cover_every_demo_job():
    from scripts.seed_demo import NEW_JOBS, SEED_REQUIREMENTS

    assert set(SEED_REQUIREMENTS) == {spec["title"] for spec in NEW_JOBS}
    for title, raw in SEED_REQUIREMENTS.items():
        assert parse_requirements(raw) is not None, title
        assert JobRequirements.model_validate(raw).model_dump() == raw, title


# --- through the API ----------------------------------------------------------


REQS = {
    "must_have_skills": ["Python", "Rust"],
    "nice_to_have_skills": ["Airflow"],
    "min_years": 6,
    "max_years": 12,
    "min_education": "master",
}


def _job_body(**overrides):
    body = {
        "title": "Requirements Test Engineer",
        "department": "Engineering",
        "job_overview": "Tests requirement caps.",
        "required_qualifications": "Python",
        "status": "draft",
        "skills": ["Python", "SQL"],
        "requirements": REQS,
    }
    body.update(overrides)
    return body


def test_job_api_round_trips_requirements(admin_client):
    created = admin_client.post("/api/jobs/", json=_job_body())
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["requirements"] == REQS

    fetched = admin_client.get(f"/api/jobs/{job['id']}").json()
    assert fetched["requirements"] == REQS

    cleared = admin_client.put(
        f"/api/jobs/{job['id']}", json=_job_body(requirements={"must_have_skills": []})
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["requirements"] is None

    too_many = admin_client.post(
        "/api/jobs/", json=_job_body(requirements={"must_have_skills": [f"s{i}" for i in range(21)]})
    )
    assert too_many.status_code == 422


def test_trace_explains_the_cap_using_recorded_history(admin_client, db_session):
    """End to end: a job with requirements, a candidate whose years and degree
    come from candidate_experience / candidate_education rows, and the trace
    saying which requirements were missed."""
    job = admin_client.post("/api/jobs/", json=_job_body(status="open")).json()

    cid = "00000000-0000-4000-8000-0000000a11e1"
    db_session.add(
        Candidate(
            id=cid,
            first_name="Req",
            last_name="Tester",
            email="req.tester@recruitiq-seed.example.com",
            current_position="Requirements Test Engineer",
            created_at=datetime(2026, 1, 1),
        )
    )
    db_session.flush()
    for skill in ("Python", "SQL", "Airflow"):
        db_session.add(CandidateSkill(candidate_id=cid, skill_name=skill))
    db_session.execute(
        text(
            "INSERT INTO candidate_experience (candidate_id, company, position, start_date, end_date) "
            "VALUES (:cid, 'Acme', 'Engineer', :start, :end)"
        ),
        {"cid": cid, "start": date(2020, 1, 1), "end": date(2023, 1, 1)},
    )
    db_session.execute(
        text("INSERT INTO candidate_education (candidate_id, institution, degree) VALUES (:cid, 'State U', 'BSc')"),
        {"cid": cid},
    )
    db_session.commit()

    response = admin_client.get(f"/api/transparency/match-trace?job_id={job['id']}&candidate_id={cid}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job"]["requirements"]["must_have_skills"] == ["Python", "Rust"]
    trace = body["traces"][0]
    req = trace["requirements"]
    assert req["must_have"]["missing"] == ["Rust"]
    assert req["years"]["candidate_years"] == pytest.approx(3.0, abs=0.05)
    assert req["years"]["counts_as_missing"] is True
    assert req["education"] == {
        "min_education": "master",
        "candidate_education": "bachelor",
        "meets": False,
        "counts_as_missing": True,
    }
    assert req["cap"]["missing_count"] == 3
    assert req["cap"]["limit"] == 50
    assert trace["match_score"] <= 50
    assert trace["skills"]["nice_to_have_bonus"] == pytest.approx(10.0)
    assert "Missing must-have skills: Rust" in trace["explanation"]

    # The ranking agrees with the trace for this person.
    ranking = admin_client.post(
        "/api/enhanced-matching/match-candidates", json={"job_ids": [job["id"]], "min_score": 0}
    )
    assert ranking.status_code == 200, ranking.text
    ranked = {c["id"]: c for c in ranking.json()["candidates"]}
    if cid in ranked:  # the ranking stops at 10 on a loaded dev database
        assert ranked[cid]["match_score"] == pytest.approx(trace["match_score"])


def test_policy_publishes_the_requirement_rules(demo_client):
    rules = demo_client.get("/api/transparency/policy").json()["requirement_rules"]
    assert [(c["min_missing"], c["limit"]) for c in rules["caps"]] == [(2, 50.0), (1, 70.0)]
    assert rules["nice_to_have_max_bonus"] == 10.0
    assert rules["years_short_counts_as_missing"] == 2.0
