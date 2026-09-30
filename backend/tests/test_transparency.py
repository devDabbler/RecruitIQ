"""The scoring-transparency endpoints and the contract behind them.

Three things matter here beyond "the routes answer":

* The trace is the computation. `/match-trace` must produce the same number
  for a candidate that `/enhanced-matching/match-candidates` ranks them by,
  and the trace's own intermediates must add up to that number.
* The fields the policy says are never scored really are never scored.
  `test_unscored_fields_do_not_move_the_score` rewrites every one of them and
  asserts the score is bit-identical, so the published list is a checked
  claim rather than a comment.
* The traces carry no contact details. That property is what made it safe to
  open these endpoints to the demo role (2026-09-28), so it is pinned by
  `test_traces_carry_no_contact_details` rather than left as an argument in
  a code review.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from backend.models.models import Candidate, CandidateSkill, Job
from backend.services.matching_integrator import (
    UNSCORED_CANDIDATE_FIELDS,
    WEIGHT_TIERS,
    MatchingIntegrator,
    select_weight_tier,
)


# --- access -----------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/transparency/policy",
        "/api/transparency/match-trace?job_id=1",
        "/api/transparency/search-trace?q=python",
    ],
)
def test_anonymous_is_refused(client, path):
    """A token is still required. Site visitors always hold a demo token (the
    proxy issues one), so this only shuts out bare tokenless scraping."""
    assert client.get(path).status_code == 401


def test_demo_role_can_read_the_policy(demo_client):
    """Transparency is demo-visible by design: the dataset is synthetic and
    the traces show less about a person than the demo's own candidate pages."""
    response = demo_client.get("/api/transparency/policy")
    assert response.status_code == 200
    assert response.json()["weight_tiers"]


def test_demo_role_can_trace_a_search(demo_client):
    response = demo_client.get("/api/transparency/search-trace?q=python")
    assert response.status_code == 200
    assert "hits" in response.json()


# --- policy -----------------------------------------------------------------


def test_policy_publishes_the_tiers_the_ranker_uses(admin_client):
    response = admin_client.get("/api/transparency/policy")
    assert response.status_code == 200
    policy = response.json()

    assert [t["name"] for t in policy["weight_tiers"]] == [t["name"] for t in WEIGHT_TIERS]
    for tier in policy["weight_tiers"]:
        assert sum(tier["weights"].values()) == pytest.approx(1.0)
        assert 0 < tier["multiplier"] <= 1.0

    never = {f["field"] for f in policy["candidate_fields_never_scored"]}
    for field in ("first_name", "last_name", "email", "location", "notes", "status"):
        assert field in never
    assert policy["fields_not_collected"]
    assert policy["search_relevance_floor"] == 0.35
    assert policy["search_relevance_bands"] == {"strong": 0.65, "moderate": 0.45}


def test_policy_constants_match_the_enhancer():
    """The three numbers the policy restates from matching_enhancer."""
    enhancer = MatchingIntegrator(embedding_model=None).enhancer

    penalised = enhancer.cross_domain_skill_penalty_details(100.0, "Data Scientist", "Software Engineer")
    assert penalised["applied"] and penalised["score"] == pytest.approx(30.0)

    high = enhancer.role_match_details("Data Scientist", "", "Sales Manager")
    assert high["relationship"] == "highly_incompatible" and high["score"] <= 12.0
    moderate = enhancer.role_match_details("Data Scientist", "", "Software Engineer")
    assert moderate["relationship"] == "moderately_incompatible" and moderate["score"] <= 20.0


def test_tier_selection_boundaries():
    assert select_weight_tier(0)["name"] == "severe_role_mismatch"
    assert select_weight_tier(29.999)["name"] == "severe_role_mismatch"
    assert select_weight_tier(30)["name"] == "moderate_role_mismatch"
    assert select_weight_tier(49.999)["name"] == "moderate_role_mismatch"
    assert select_weight_tier(50)["name"] == "standard"
    assert select_weight_tier(100)["name"] == "standard"


# --- match trace ------------------------------------------------------------


@pytest.fixture(scope="module")
def full_trace(admin_client, seed) -> dict:
    """One scoring pass over the whole database, shared by the tests below.

    A pass scores every candidate, and on a loaded dev database that is a few
    hundred title embeddings; fetching it once keeps the module fast."""
    response = admin_client.get(f"/api/transparency/match-trace?job_id={seed['job_id']}&limit=500")
    assert response.status_code == 200, response.text
    return response.json()


def test_match_trace_is_the_live_ranking(admin_client, seed, full_trace):
    job_id = seed["job_id"]
    assert full_trace["job"]["id"] == job_id
    assert full_trace["candidates_scored"] == len(full_trace["traces"])

    ranking = admin_client.post(
        "/api/enhanced-matching/match-candidates",
        json={"job_ids": [job_id], "min_score": 0},
    )
    assert ranking.status_code == 200, ranking.text
    # The ranking endpoint stops at 10; the trace does not. Compare the people
    # the ranking did return, which must include our seeded three when the
    # database is otherwise empty (CI) and may not when it is not (dev).
    ranked = {c["id"]: c for c in ranking.json()["candidates"]}
    assert ranked, "ranking returned nobody"

    by_id = {t["candidate_id"]: t for t in full_trace["traces"]}
    for cid, row in ranked.items():
        assert cid in by_id
        assert by_id[cid]["match_score"] == pytest.approx(row["match_score"])
        assert by_id[cid]["skills"]["score"] == pytest.approx(row["skill_match_score"])
        assert by_id[cid]["role"]["score"] == pytest.approx(row["role_match_score"])
        assert by_id[cid]["experience"]["score"] == pytest.approx(row["experience_match_score"])
        assert by_id[cid]["explanation"] == row["match_explanation"]
    for cid in seed["candidate_ids"]:
        assert cid in by_id


def test_trace_intermediates_add_up(full_trace):
    body = full_trace
    ranks = [t["rank"] for t in body["traces"]]
    assert ranks == sorted(ranks)
    scores = [t["match_score"] for t in body["traces"]]
    assert scores == sorted(scores, reverse=True)

    for t in body["traces"]:
        w = t["tier"]["weights"]
        weighted = (
            t["skills"]["score"] * w["skill"]
            + t["role"]["score"] * w["role"]
            + t["experience"]["score"] * w["experience"]
        ) * t["tier"]["multiplier"]
        assert t["weighted_score"] == pytest.approx(weighted)
        expected = weighted * (t["final_penalty_multiplier"] if t["final_penalty_applied"] else 1.0)
        assert t["match_score"] == pytest.approx(expected)
        assert t["above_threshold"] == (t["match_score"] >= body["threshold"])

        # The skill step accounts for every job skill exactly once.
        accounted = t["skills"]["exact"] + t["skills"]["partial"] + t["skills"]["missing"]
        assert sorted(accounted) == sorted(t["skills"]["job_skills"])
        if t["skills"]["penalty_applied"]:
            assert t["skills"]["score"] == pytest.approx(t["skills"]["raw_score"] * t["skills"]["penalty_factor"])
        else:
            assert t["skills"]["score"] == pytest.approx(t["skills"]["raw_score"])


def _keys_in(value) -> set:
    """Every dict key anywhere in a JSON-shaped value."""
    found = set()
    if isinstance(value, dict):
        for key, inner in value.items():
            found.add(key)
            found |= _keys_in(inner)
    elif isinstance(value, list):
        for inner in value:
            found |= _keys_in(inner)
    return found


def test_traces_carry_no_contact_details(demo_client, full_trace):
    """The property that makes demo access safe: no email, phone, or notes
    anywhere in a trace, so these endpoints reveal strictly less about a
    person than the demo-visible candidate and matching screens already do."""
    banned = {"email", "phone", "notes"}
    assert not _keys_in(full_trace) & banned

    search = demo_client.get("/api/transparency/search-trace?q=python").json()
    assert not _keys_in(search) & banned


def test_single_candidate_trace_keeps_its_rank(admin_client, seed, full_trace):
    cid = seed["candidate_ids"][-1]
    expected = next(t for t in full_trace["traces"] if t["candidate_id"] == cid)

    one = admin_client.get(f"/api/transparency/match-trace?job_id={seed['job_id']}&candidate_id={cid}")
    assert one.status_code == 200
    traces = one.json()["traces"]
    assert len(traces) == 1
    assert traces[0]["rank"] == expected["rank"]
    assert traces[0]["match_score"] == pytest.approx(expected["match_score"])


def test_unknown_job_and_candidate_are_404(admin_client, seed):
    assert admin_client.get("/api/transparency/match-trace?job_id=999999").status_code == 404
    missing = admin_client.get(
        f"/api/transparency/match-trace?job_id={seed['job_id']}&candidate_id=no-such-candidate"
    )
    assert missing.status_code == 404


# --- the never-scored contract ---------------------------------------------


def _job() -> Job:
    return Job(
        title="Senior Data Engineer",
        job_overview="Own the analytics pipeline.",
        required_qualifications="Python, SQL, dbt, 5+ years",
        skills="Python,SQL,dbt,Airflow",
        status="open",
    )


def _candidate(**overrides) -> Candidate:
    fields = dict(
        created_at=datetime(2025, 1, 1),
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        phone="+1-555-0100",
        location="London, UK",
        headline="Data engineer",
        notes="",
        current_company="Analytical Engines",
        source="referral",
        status="active",
        position_applied="Senior Data Engineer",
        current_position="Data Engineer",
    )
    fields.update(overrides)
    candidate = Candidate(**fields)
    candidate.skills = [CandidateSkill(skill_name=s) for s in ("Python", "SQL", "Spark")]
    return candidate


SCORE_KEYS = ("match_score", "skill_match_score", "role_match_score", "experience_match_score")


def test_unscored_fields_do_not_move_the_score():
    integrator = MatchingIntegrator(embedding_model=None)
    baseline = integrator.score_pair(_job(), _candidate())

    rewritten = _candidate(
        created_at=datetime(2026, 6, 30),
        first_name="Zbigniew",
        last_name="Brzezinski-Okonkwo",
        email="someone.else@example.org",
        phone="+44 20 7946 0000",
        location="Lagos, Nigeria",
        headline="Mother of three, 58, returning to work after illness",
        notes="Recruiter thinks this person is a poor culture fit.",
        current_company="Unknown Startup",
        source="job_board",
        status="rejected",
        position_applied="Chief Executive Officer",
    )
    for field in UNSCORED_CANDIDATE_FIELDS:
        name = field["field"]
        if hasattr(Candidate, name):
            assert getattr(rewritten, name) != getattr(_candidate(), name), name
    changed = integrator.score_pair(_job(), rewritten)

    for key in SCORE_KEYS:
        assert changed[key] == baseline[key], key
    assert changed["tier"] == baseline["tier"]
    assert changed["skills"] == baseline["skills"]
    assert changed["experience"] == baseline["experience"]


def test_scored_fields_do_move_the_score():
    """The converse, so the previous test cannot pass by scoring nothing."""
    integrator = MatchingIntegrator(embedding_model=None)
    baseline = integrator.score_pair(_job(), _candidate())
    other_role = integrator.score_pair(_job(), _candidate(current_position="Sales Manager"))
    assert other_role["match_score"] < baseline["match_score"]

    fewer_skills = _candidate()
    fewer_skills.skills = [CandidateSkill(skill_name="Excel")]
    assert integrator.score_pair(_job(), fewer_skills)["match_score"] < baseline["match_score"]


# --- search trace -----------------------------------------------------------


def test_search_trace_shape_and_degradation_flag(admin_client):
    """CI runs with the embedding endpoint unreachable on purpose. The adapter
    then answers with deterministic placeholder vectors rather than failing,
    so the trace must still be well-formed and must say the numbers are not
    semantic (`embedding_degraded`). With a reachable model the same request
    returns real similarities and the flag is false."""
    response = admin_client.get("/api/transparency/search-trace?q=python%20data%20engineer&location=anywhere")
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body["embedding_degraded"], bool)
    assert body["relevance_floor"] == 0.35
    assert body["location_ignored"] is True  # "anywhere" is not a filter
    assert body["location_patterns"] == []
    assert body["evidence_fields"] == ["position", "company", "headline", "skills"]
    for hit in body["hits"]:
        # What the assistant is given is never weak, and a moderate hit
        # always says which words it matched on.
        assert hit["similarity"] >= body["relevance_floor"]
        assert hit["relevance"] in ("strong", "moderate")
        assert hit["relevance"] == "strong" or hit["matched_on"]
    for hit in body["kept_out"]:
        assert hit["relevance"] in ("strong", "moderate", "weak")
        assert isinstance(hit["matched_on"], list)
