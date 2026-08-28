"""The seed script's determinism guarantees (Phase 3 spec §7).

These cover the two ways `scripts/seed_demo.py` could quietly stop being
idempotent. Both were live bugs during authoring, so they are regression tests
rather than speculative ones.
"""
import random
import subprocess
import sys

from scripts.seed_demo import PIPELINE_WEIGHTS, SEED_FUNNEL, _weighted_statuses, stable_index


def test_stable_index_survives_a_new_interpreter():
    """The bucket must not move between processes.

    `hash()` on a str is salted per process unless PYTHONHASHSEED is pinned, so
    a `hash(id) % n` bucket picks a different job on every run. That is the same
    failure that made openapi.json irreproducible in Phase 3a.
    """
    expected = stable_index("candidate-abc", 8)
    out = subprocess.run(
        [sys.executable, "-c",
         "from scripts.seed_demo import stable_index; print(stable_index('candidate-abc', 8))"],
        capture_output=True, text=True, check=True,
    )
    assert int(out.stdout.strip()) == expected


def test_stable_index_stays_in_range():
    for modulus in (1, 3, 8, 40):
        for key in ("a", "b", "some-uuid-like-value", ""):
            assert 0 <= stable_index(key, modulus) < modulus


def test_weighted_statuses_covers_every_stage():
    """A funnel with an empty column renders as a broken Dashboard widget."""
    statuses = _weighted_statuses(random.Random(SEED_FUNNEL), 40)
    assert len(statuses) == 40
    for status, _ in PIPELINE_WEIGHTS:
        assert status in statuses, f"no candidate landed in {status!r}"


def test_weighted_statuses_is_reproducible():
    a = _weighted_statuses(random.Random(SEED_FUNNEL), 40)
    b = _weighted_statuses(random.Random(SEED_FUNNEL), 40)
    assert a == b


def test_weighted_statuses_handles_small_and_zero_n():
    assert _weighted_statuses(random.Random(SEED_FUNNEL), 0) == []
    assert len(_weighted_statuses(random.Random(SEED_FUNNEL), 3)) == 3
