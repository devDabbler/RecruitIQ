"""The seed script's determinism guarantees (Phase 3 spec §7).

These cover the two ways `scripts/seed_demo.py` could quietly stop being
idempotent. Both were live bugs during authoring, so they are regression tests
rather than speculative ones.
"""
import random
import subprocess
import sys
from datetime import datetime, timedelta

from backend.utils.tags import normalize_tag
from scripts.seed_demo import (
    PIPELINE_WEIGHTS,
    SEED_FUNNEL,
    SEED_NOTES,
    SEED_TAGS,
    _weighted_statuses,
    seed_note_for,
    seed_tags_for,
    stable_index,
    stage_timeline,
)


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


def test_seed_tags_are_normalized_and_stable():
    for tag in SEED_TAGS:
        assert normalize_tag(tag) == tag
    emails = [f"person{i}@demo.recruitiq.dev" for i in range(40)]
    first = [seed_tags_for(e) for e in emails]
    assert first == [seed_tags_for(e) for e in emails]
    assert sum(1 for tags in first if tags) >= 15  # a believable share are tagged
    assert all(len(tags) <= 2 for tags in first)


def test_seed_notes_are_stable_and_from_the_fixed_list():
    emails = [f"person{i}@demo.recruitiq.dev" for i in range(40)]
    notes = [seed_note_for(e) for e in emails]
    assert notes == [seed_note_for(e) for e in emails]
    assert all(n is None or n in SEED_NOTES for n in notes)
    assert sum(1 for n in notes if n) >= 8


NOW = datetime(2026, 3, 15, 12, 0, 0)

ROUNDS = [
    "resume_submitted",
    "hm_review",
    "technical_written",
    "technical_interview",
    "problem_solving",
    "case_study",
    "hr_screen",
    "offer",
    "offer_accepted",
]


def _rows(statuses, outcomes=("pending", "pending")):
    rows = [(key, "round", status) for key, status in zip(ROUNDS, statuses)]
    return rows + [("offer_declined", "outcome", outcomes[0]), ("hired", "outcome", outcomes[1])]


def test_timeline_for_an_active_application_is_contiguous():
    rows = _rows(["passed", "passed", "in_progress"] + ["pending"] * 6)
    applied, spans = stage_timeline("cand-1:7", rows, NOW)
    (s0, c0), (s1, c1), (s2, c2) = spans[:3]
    assert applied < s0 < c0 == s1 < c1 == s2 < NOW
    assert c2 is None
    assert all(span == (None, None) for span in spans[3:])


def test_timeline_for_a_rejected_application():
    rows = _rows(["passed", "failed"] + ["skipped"] * 7, outcomes=("skipped", "skipped"))
    applied, spans = stage_timeline("cand-2:7", rows, NOW)
    end = spans[1][1]
    assert spans[0][1] == spans[1][0]
    assert end <= NOW - timedelta(days=2)
    # Skipped rows never started; they ended when the application did.
    assert all(span == (None, end) for span in spans[2:])


def test_timeline_for_a_hire_ends_on_the_outcome():
    rows = _rows(["passed"] * 9, outcomes=("skipped", "passed"))
    applied, spans = stage_timeline("cand-3:7", rows, NOW)
    end = spans[8][1]
    assert spans[10] == (end, end)  # Hired
    assert spans[9] == (None, end)  # Offer declined, skipped
    for earlier, later in zip(spans[:8], spans[1:9]):
        assert earlier[1] == later[0]


def test_timeline_is_deterministic_and_varies_by_application():
    rows = _rows(["passed", "in_progress"] + ["pending"] * 7)
    assert stage_timeline("cand-4:7", rows, NOW) == stage_timeline("cand-4:7", rows, NOW)
    starts = {stage_timeline(f"cand-{i}:7", rows, NOW)[1][1][0] for i in range(20)}
    assert len(starts) > 1


def test_some_active_applications_have_not_moved_in_a_week():
    rows = _rows(["in_progress"] + ["pending"] * 8)
    waits = [(NOW - stage_timeline(f"c{i}:1", rows, NOW)[1][0][0]).days for i in range(200)]
    assert any(w >= 8 for w in waits) and any(w < 7 for w in waits)
    assert max(waits) <= 14


def test_nothing_reached_means_nothing_to_lay_out():
    applied, spans = stage_timeline("cand-5:7", _rows(["pending"] * 9), NOW)
    assert applied is None


def test_spread_rewrites_flat_rows_once_and_never_touches_moved_ones(db_session, seed):
    from backend.models.models import Job, JobApplication
    from backend.services import pipeline_service as ps
    from scripts.seed_demo import _spread_stage_timeline

    job = Job(
        title="Seed Spread Test Role",
        department="QA",
        job_overview="Exists to test the seed's timestamp layout.",
        required_qualifications="None",
        location="Remote",
        location_type="remote",
        job_type="full_time",
        experience_level="mid",
        status="open",
        job_metadata={},
        views=0,
        applications=0,
    )
    db_session.add(job)
    db_session.flush()
    flat_at = datetime(2025, 3, 1, 9, 0, 0)
    apps = []
    for candidate_id in (seed["candidate_ids"][1], seed["candidate_ids"][2]):
        app = JobApplication(job_id=job.id, candidate_id=candidate_id, status="active", applied_at=flat_at, source="direct")
        db_session.add(app)
        db_session.flush()
        ps.ensure_application_stages(db_session, app)
        apps.append(app)
    flat, moved = apps
    ps.advance(db_session, moved)  # a person moved this one: real timestamps now

    when = datetime(2025, 6, 1, 12, 0, 0)
    assert _spread_stage_timeline(db_session, flat, when) is True
    db_session.flush()
    first = sorted(flat.stages, key=lambda r: r.stage.position)[0]
    assert first.started_at > flat.applied_at
    snapshot = sorted((r.stage_id, r.started_at, r.completed_at) for r in flat.stages) + [flat.applied_at]

    assert _spread_stage_timeline(db_session, flat, when) is False
    assert sorted((r.stage_id, r.started_at, r.completed_at) for r in flat.stages) + [flat.applied_at] == snapshot

    before = sorted((r.stage_id, r.started_at, r.completed_at) for r in moved.stages)
    assert _spread_stage_timeline(db_session, moved, when) is False
    assert sorted((r.stage_id, r.started_at, r.completed_at) for r in moved.stages) == before

    db_session.delete(job)
    db_session.commit()


def _flat_application(db_session, job, candidate_id, flat_at):
    from backend.models.models import JobApplication
    from backend.services import pipeline_service as ps

    app = JobApplication(job_id=job.id, candidate_id=candidate_id, status="active", applied_at=flat_at, source="direct")
    db_session.add(app)
    db_session.flush()
    ps.ensure_application_stages(db_session, app)
    return app


def _test_job(db_session, title):
    from backend.models.models import Job

    job = Job(
        title=title,
        department="QA",
        job_overview="Exists to test the seed's timestamp layout.",
        required_qualifications="None",
        location="Remote",
        location_type="remote",
        job_type="full_time",
        experience_level="mid",
        status="open",
        job_metadata={},
        views=0,
        applications=0,
    )
    db_session.add(job)
    db_session.flush()
    return job


def test_spread_moves_seeded_interviews_and_feedback_with_their_stage(db_session, seed):
    """Prod's interviews were seeded from the flat timestamps; after a spread
    they must not read as submitted before their round started."""
    from backend.models.models import Feedback, Interview, User
    from scripts.seed_demo import _spread_stage_timeline

    job = _test_job(db_session, "Seed Interview Realign Role")
    flat_at = datetime(2025, 3, 1, 9, 0, 0)
    app = _flat_application(db_session, job, seed["candidate_ids"][1], flat_at)
    first = sorted(app.stages, key=lambda r: r.stage.position)[0]
    # Shape it like a seeded "passed resume, in HM review" application.
    second = sorted(app.stages, key=lambda r: r.stage.position)[1]
    first.status, first.completed_at = "passed", flat_at
    second.status, second.started_at = "in_progress", flat_at
    person = User(email="realign@recruitiq-seed.example.com", role="interviewer", name="Realign Person")
    db_session.add(person)
    db_session.flush()
    seeded = Interview(application_stage_id=first.id, interviewer_id=person.id, created_at=flat_at)
    seeded.feedback = Feedback(rating=4, recommendation="hire", submitted_at=flat_at)
    by_hand_at = datetime(2025, 3, 2, 15, 30, 0)
    by_hand = Interview(application_stage_id=second.id, interviewer_id=person.id, created_at=by_hand_at)
    db_session.add_all([seeded, by_hand])
    db_session.flush()

    assert _spread_stage_timeline(db_session, app, datetime(2025, 6, 1, 12, 0, 0)) is True
    db_session.flush()
    assert seeded.created_at == first.started_at
    assert seeded.feedback.submitted_at == first.completed_at > first.started_at
    assert by_hand.created_at == by_hand_at  # not seeded: left alone

    db_session.delete(job)
    db_session.delete(person)
    db_session.commit()


def test_seed_timelines_only_touches_seeded_applications(db_session, seed):
    from scripts.seed_demo import SEEDED_APPLICATION_NOTE, seed_timelines

    job = _test_job(db_session, "Seed Timelines Only Role")
    flat_at = datetime(2025, 3, 1, 9, 0, 0)
    mine = _flat_application(db_session, job, seed["candidate_ids"][1], flat_at)
    mine.notes = f"{SEEDED_APPLICATION_NOTE} (active)."
    other = _flat_application(db_session, job, seed["candidate_ids"][2], flat_at)
    db_session.flush()

    now = datetime(2025, 6, 1, 12, 0, 0)
    seed_timelines(db_session, now)
    assert mine.applied_at != flat_at
    assert other.applied_at == flat_at
    assert all(r.started_at in (None, flat_at) for r in other.stages)
    assert seed_timelines(db_session, now) == 0  # a re-run is a no-op

    db_session.delete(job)
    db_session.commit()
