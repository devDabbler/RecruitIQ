"""Scoring a resume against a real requisition rather than a guessed one.

The problem this covers: a free-text target role is resolved by a pgvector
lookup of similar jobs, and when that finds too little it falls back to a static
per-role skill list. A title that is not in the database is therefore scored
against an invention. Passing `job_id` replaces that with the job's own skills.
"""
from __future__ import annotations

import numpy as np
import pytest

from backend.services.agent_framework.agents.resume_processing_agent import (
    _is_ai_role,
    _job_skills_from,
)
from backend.services.matching_enhancer import MatchingEnhancer


# --- the AI-role substring bug ----------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "AI Engineer",
        "Gen AI Engineer",
        "Machine Learning Engineer",
        "Senior ML Engineer",
        "NLP Researcher",
        "artificial intelligence lead",
    ],
)
def test_ai_roles_are_recognised(title):
    assert _is_ai_role(title)


@pytest.mark.parametrize(
    "title",
    [
        # Every one of these contains "ai" and used to collect the AI scoring
        # bonus: retAIl, mAIntenance, trAIner, pAId.
        "Retail Store Manager",
        "Maintenance Technician",
        "Corporate Trainer",
        "Paid Media Specialist",
        "Chair of the Board",
        "Account Executive",
    ],
)
def test_non_ai_roles_are_not_mistaken_for_ai_roles(title):
    assert not _is_ai_role(title)


def test_missing_title_is_not_an_ai_role():
    assert not _is_ai_role(None)
    assert not _is_ai_role("")


# --- reading a job's own skills ---------------------------------------------


def test_job_skills_parsed_from_a_comma_separated_column():
    assert _job_skills_from({"skills": "Python, SQL,dbt"}) == ["Python", "SQL", "dbt"]


def test_job_skills_parsed_from_a_list():
    assert _job_skills_from({"skills": ["Python", "SQL"]}) == ["Python", "SQL"]


@pytest.mark.parametrize(
    "job_data",
    [None, {}, {"skills": None}, {"skills": ""}, {"skills": []}, {"skills": " , "}],
    ids=["none", "empty-dict", "null", "empty-string", "empty-list", "separators-only"],
)
def test_job_with_no_usable_skills_reads_as_none_not_empty(job_data):
    """None means "fall back to the market path".

    An empty list would instead be taken as "this role requires no skills" and
    would score every resume at zero overlap.
    """
    assert _job_skills_from(job_data) is None


# --- the embedding memo -----------------------------------------------------


class CountingEmbeddings:
    """Deterministic fake embedder that records how often it was called."""

    def __init__(self):
        self.calls = []

    def embed_query(self, text: str):
        self.calls.append(text)
        # Stable pseudo-vector derived from the text, so identical input gives
        # identical output and the scores below are reproducible.
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        return rng.random(64).tolist()


def test_repeated_embeddings_are_computed_once():
    """Scoring one job against N candidates re-embedded the job title N times."""
    model = CountingEmbeddings()
    enhancer = MatchingEnhancer(embedding_model=model)

    candidates = ["Data Engineer", "Software Engineer", "Data Engineer", "ML Engineer"]
    for position in candidates:
        enhancer.calculate_role_match_score("Senior Data Engineer", "", position)

    # Without the memo this is 8 calls: two per candidate. With it, one per
    # distinct string: the job title plus three distinct positions.
    assert len(model.calls) == 4
    assert model.calls.count("senior data engineer") == 1


def test_memoised_scores_match_unmemoised_ones():
    """The memo is a performance change and must not move any number."""
    pairs = [
        ("Senior Data Engineer", "Data Engineer"),
        ("Machine Learning Engineer", "Research Scientist"),
        ("Retail Store Manager", "Data Engineer"),
    ]

    fresh_scores = []
    for title, position in pairs:
        # A brand-new enhancer per pair, so nothing is ever served from cache.
        enhancer = MatchingEnhancer(embedding_model=CountingEmbeddings())
        fresh_scores.append(enhancer.calculate_role_match_score(title, "", position))

    shared = MatchingEnhancer(embedding_model=CountingEmbeddings())
    # Run twice so the second pass is served entirely from the memo.
    shared_scores = [shared.calculate_role_match_score(t, "", p) for t, p in pairs]
    repeat_scores = [shared.calculate_role_match_score(t, "", p) for t, p in pairs]

    assert shared_scores == fresh_scores
    assert repeat_scores == fresh_scores


def test_embedding_cache_is_bounded():
    """A long-lived process must not accumulate vectors without limit."""
    from backend.services.matching_enhancer import _EMBEDDING_CACHE_MAX

    enhancer = MatchingEnhancer(embedding_model=CountingEmbeddings())
    for i in range(_EMBEDDING_CACHE_MAX + 50):
        enhancer._embed(f"role number {i}")

    assert len(enhancer._embedding_cache) == _EMBEDDING_CACHE_MAX


# --- the API surface --------------------------------------------------------


def test_parsing_against_an_unknown_job_is_a_client_error(client):
    """A bad job_id must not silently degrade into the market estimate.

    Also a regression guard on status code: the handler wraps its body in a
    blanket `except Exception` that returns 500, so this 400 only survives
    because the lookup happens before that block.
    """
    response = client.post(
        "/api/resume/parse",
        files={"file": ("cv.txt", b"Ada Lovelace\nEngineer", "text/plain")},
        data={"job_id": "99999999"},
    )
    assert response.status_code == 400
    assert "99999999" in response.json()["detail"]
