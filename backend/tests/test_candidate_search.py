"""Regression tests for `GET /api/candidates/` keyword search.

The Candidates screen offers to "search by name, skill, or position", but the
filter behind it only ever looked at first_name/last_name/email. Typing
"Python" into a database of forty engineers returned nothing, silently — the
route answered 200 with an empty list, so there was no error anywhere to notice.
These tests pin the widened filter down.

Assertions are membership-based, not count-based: the suite runs against the
dev database, which also holds the demo dataset, so any exact total would be a
number that happens to be true today.
"""
from __future__ import annotations

import pytest

from backend.models.models import CandidateSkill
from backend.tests.conftest import SEED_EPOCH

# Two skills attached to Ada for the duration of a test.
#
# The first appears nowhere else in either dataset, so a search for it can only
# match her. The second deliberately overlaps her `current_company`
# ("Analytical Engines"), which makes it the case that catches a JOIN-based
# implementation: two matching branches for one candidate must still yield one
# row.
UNIQUE_SKILL = "Difference Engine Assembly"
OVERLAPPING_SKILL = "Analytical Engines Tooling"


@pytest.fixture
def ada_skills(db_session, seed):
    """Give the first seeded candidate two extra skills, then take them back."""
    candidate_id = seed["candidate_ids"][0]
    rows = [
        CandidateSkill(
            candidate_id=candidate_id,
            skill_name=name,
            proficiency="advanced",
            years_of_experience=5,
            created_at=SEED_EPOCH,
            updated_at=SEED_EPOCH,
        )
        for name in (UNIQUE_SKILL, OVERLAPPING_SKILL)
    ]
    db_session.add_all(rows)
    db_session.flush()
    try:
        yield candidate_id
    finally:
        for row in rows:
            db_session.delete(row)
        db_session.flush()


def search(client, keyword: str, **params) -> dict:
    response = client.get(
        "/api/candidates/", params={"keyword": keyword, "page_size": 100, **params}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_keyword_matches_a_skill(client, ada_skills):
    """The query that matters most: who knows X."""
    body = search(client, UNIQUE_SKILL)

    assert [c["id"] for c in body["results"]] == [ada_skills]
    assert body["total"] == 1


def test_keyword_matches_current_company(client, seed):
    ids = [c["id"] for c in search(client, "Analytical Engines")["results"]]

    assert seed["candidate_ids"][0] in ids


def test_keyword_matches_current_position(client, seed):
    ids = [c["id"] for c in search(client, "Research Scientist")["results"]]

    # Alan Turing. The demo dataset may hold other research scientists, hence
    # membership rather than equality.
    assert seed["candidate_ids"][2] in ids


def test_keyword_still_matches_name_and_email(client, seed):
    """The behaviour that already worked, kept."""
    by_name = [c["id"] for c in search(client, "Lovelace")["results"]]
    by_email = [c["id"] for c in search(client, "grace@recruitiq-seed")["results"]]

    assert by_name == [seed["candidate_ids"][0]]
    assert by_email == [seed["candidate_ids"][1]]


def test_a_candidate_matching_twice_is_returned_once(client, ada_skills):
    """`total` drives pagination, so a duplicated row is a paging bug too.

    "Analytical Engines" matches Ada's company *and* one of her skills. Joining
    candidate_skills would return her twice and count her twice.
    """
    body = search(client, "Analytical Engines")
    ids = [c["id"] for c in body["results"]]

    assert ids.count(ada_skills) == 1
    assert len(ids) == len(set(ids))
    assert body["total"] == len(ids)


def test_keyword_with_no_match_returns_empty(client):
    body = search(client, "zzz-no-such-candidate-zzz")

    assert body["results"] == []
    assert body["total"] == 0
