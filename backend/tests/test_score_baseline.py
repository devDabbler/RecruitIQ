"""Jobs without structured requirements score exactly as they did before
Track 2 Phase 1 added them.

`golden/score_pair_baseline.json` was written by the scoring code as it stood
before requirements existed, over every seeded job x seeded candidate pair,
once with no embedding model (role fit falls back to its neutral 30) and once
with a deterministic fake embedder (so the semantic path and the role-family
rules are exercised too). Any change that moves one of those numbers for a job
with no requirements fails here.

Regenerate only on purpose: UPDATE_SCORE_BASELINE=1 pytest this file.
"""
from __future__ import annotations

import json
import os
import zlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from backend.models.models import Candidate, CandidateSkill, Job
from backend.services.matching_integrator import MatchingIntegrator
from scripts.seed_demo import NEW_CANDIDATES, NEW_JOBS

BASELINE = Path(__file__).parent / "golden" / "score_pair_baseline.json"
KEYS = ("match_score", "skill_match_score", "role_match_score", "experience_match_score", "match_explanation")


class FakeEmbedder:
    """Same vector for the same text in every process (crc32, not hash())."""

    is_degraded = False

    def embed_query(self, text: str):
        rng = np.random.RandomState(zlib.crc32(text.encode("utf-8")))
        return rng.rand(16).tolist()


def _jobs():
    # No requirements: the seed's SEED_REQUIREMENTS are deliberately not applied.
    return [Job(**spec, status="open") for spec in NEW_JOBS]


def _candidates():
    out = []
    for first, last, location, headline, applied, current, company, skills in NEW_CANDIDATES:
        candidate = Candidate(
            id=f"{first}-{last}".lower(),
            first_name=first,
            last_name=last,
            location=location,
            headline=headline,
            position_applied=applied,
            current_position=current,
            current_company=company,
            created_at=datetime(2026, 1, 1),
        )
        candidate.skills = [CandidateSkill(skill_name=s) for s in skills]
        out.append(candidate)
    return out


def _snapshot() -> dict:
    result = {}
    for label, model in (("no_embeddings", None), ("fake_embeddings", FakeEmbedder())):
        integrator = MatchingIntegrator(embedding_model=model)
        rows = {}
        for job in _jobs():
            for candidate in _candidates():
                trace = integrator.score_pair(job, candidate)
                rows[f"{job.title} | {candidate.id}"] = {key: trace[key] for key in KEYS}
        result[label] = rows
    return result


def test_jobs_without_requirements_score_exactly_as_before():
    current = _snapshot()
    if os.environ.get("UPDATE_SCORE_BASELINE") == "1":
        BASELINE.write_text(json.dumps(current, indent=1, sort_keys=True), encoding="utf-8")
        pytest.skip("baseline rewritten")

    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert current.keys() == expected.keys()
    for label in expected:
        assert current[label].keys() == expected[label].keys(), label
        for pair, scores in expected[label].items():
            got = current[label][pair]
            assert got["match_explanation"] == scores["match_explanation"], f"{label}: {pair}"
            for key in KEYS[:-1]:
                # Last-digit float noise differs between machines' BLAS (the
                # cosine in role fit); a real scoring change moves far more.
                assert got[key] == pytest.approx(scores[key], rel=0, abs=1e-9), f"{label}: {pair}: {key}"
