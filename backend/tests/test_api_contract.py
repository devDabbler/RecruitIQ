"""Golden response-shape tests for the routes the Phase 3 frontend consumes.

Why this exists: Phase 3 backfills `response_model` onto routes that ship
without one. FastAPI *filters* a response down to its declared model, so a
field the handler returns but the model omits vanishes silently — no error, no
log, just a screen that renders a blank. These tests capture the shape of every
screen-reachable response *before* the backfill and assert it unchanged after.

The golden file records structure, not values: key names and scalar types, so
the tests are stable across machines and datasets while still failing loudly if
a field disappears or changes type.

Regenerate deliberately, never casually:

    UPDATE_API_GOLDEN=1 poetry run pytest backend/tests/test_api_contract.py

and read the resulting diff line by line — every removed key is a field the
frontend can no longer see.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import pytest

from backend.tests.conftest import SEED_EMAIL_DOMAIN

GOLDEN_PATH = Path(__file__).parent / "golden" / "api_response_shapes.json"
UPDATING = os.environ.get("UPDATE_API_GOLDEN") == "1"

# Routes whose dict keys are data (skill names, for instance) rather than a
# fixed schema. Their shape collapses to the union of value types.
DYNAMIC_KEYS = "<dynamic-keys>"


def shape(value: Any, dynamic_keys: bool = False) -> Any:
    """Reduce a JSON value to its structure: keys and scalar type names."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        if dynamic_keys:
            types = sorted({_scalar_union(shape(v)) for v in value.values()})
            return {DYNAMIC_KEYS: "|".join(types) if types else "empty"}
        return {k: shape(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        if not value:
            return []
        return [_merge([shape(item) for item in value])]
    return type(value).__name__


def _scalar_union(shaped: Any) -> str:
    return shaped if isinstance(shaped, str) else json.dumps(shaped, sort_keys=True)


def _merge(shapes: list[Any]) -> Any:
    """Union a list of shapes so a nullable field in one element is not lost."""
    merged = shapes[0]
    for other in shapes[1:]:
        merged = _merge_pair(merged, other)
    return merged


def _merge_pair(a: Any, b: Any) -> Any:
    if a == b:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _merge_pair(a.get(k, "null"), b.get(k, "null")) for k in sorted({*a, *b})}
    if isinstance(a, list) and isinstance(b, list):
        if not a:
            return b
        if not b:
            return a
        return [_merge_pair(a[0], b[0])]
    # Scalars that disagree (typically a nullable field): record both, sorted so
    # the golden is order-independent.
    return "|".join(sorted({*str(a).split("|"), *str(b).split("|")}))


READ_CASE_IDS = [
    "health",
    "candidates.search",
    "candidates.detail",
    "candidates.resumes",
    "candidates.skills_breakdown",
    "jobs.search",
    "jobs.detail",
    "jobs.candidates",
    "jobs.applications_for_candidate",
    "jobs.saved_for_candidate",
    "resume.detail",
]

WRITE_CASE_IDS = [
    "jobs.create",
    "jobs.update",
    "jobs.track_view",
    "jobs.delete",
    "jobs.apply",
    "jobs.save",
    "candidates.create",
    "candidates.delete",
]


def _read_cases(seed) -> list[tuple[str, str, str, dict]]:
    """(case id, method, path, request kwargs) for side-effect-free routes."""
    candidate_id = seed["candidate_id"]
    job_id = seed["job_id"]
    resume_id = seed["resume_id"]
    return [
        ("health", "GET", "/health", {}),
        (
            "candidates.search",
            "GET",
            "/api/candidates/",
            {"params": {"keyword": SEED_EMAIL_DOMAIN, "page_size": 10}},
        ),
        ("candidates.detail", "GET", f"/api/candidates/{candidate_id}", {}),
        ("candidates.resumes", "GET", f"/api/candidates/{candidate_id}/resumes", {}),
        ("candidates.skills_breakdown", "GET", "/api/candidates/skills_breakdown", {}),
        (
            "jobs.search",
            "GET",
            "/api/jobs/",
            {"params": {"keyword": "Senior Data Engineer", "page_size": 10}},
        ),
        ("jobs.detail", "GET", f"/api/jobs/{job_id}", {}),
        ("jobs.candidates", "GET", f"/api/jobs/{job_id}/candidates", {}),
        ("jobs.applications_for_candidate", "GET", f"/api/jobs/applications/{candidate_id}", {}),
        ("jobs.saved_for_candidate", "GET", f"/api/jobs/saved/{candidate_id}", {}),
        ("resume.detail", "GET", f"/api/resume/{resume_id}", {}),
    ]


DYNAMIC_KEY_CASES = {"candidates.skills_breakdown"}


def _load_golden() -> dict:
    if not GOLDEN_PATH.exists():
        return {}
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _write_golden(data: dict) -> None:
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _capture(client, method: str, path: str, kwargs: dict, case_id: str, session) -> dict:
    response = client.request(method, path, **kwargs)
    # search_jobs assigns a Python list to Job.skills (a varchar column) purely
    # to shape its response. In production that dirty state dies with the
    # request scope; here the session is shared, so discard it before the next
    # call triggers an autoflush.
    session.expire_all()
    try:
        body = response.json()
    except ValueError:
        body = None
    return {
        "status": response.status_code,
        "shape": shape(body, dynamic_keys=case_id in DYNAMIC_KEY_CASES),
    }


@pytest.fixture(scope="session")
def read_captures(client, seed, db_session) -> dict:
    return {
        case_id: _capture(client, method, path, kwargs, case_id, db_session)
        for case_id, method, path, kwargs in _read_cases(seed)
    }


@pytest.fixture(scope="session")
def write_captures(client, seed, db_session) -> dict:
    """Exercise the mutating routes the frontend needs, with fresh payloads.

    Everything written here is undone by the outer transaction rollback in
    conftest, so these can run repeatedly against a live dev database.
    """
    suffix = uuid.uuid4().hex[:8]
    captures: dict = {}

    def cap(case_id: str, method: str, path: str, **kwargs) -> dict:
        captures[case_id] = _capture(client, method, path, kwargs, case_id, db_session)
        return captures[case_id]

    def job_payload(title: str, **overrides) -> dict:
        return {
            "title": title,
            "department": "Engineering",
            "job_overview": "Created by the API contract suite.",
            "required_qualifications": "Python",
            "location": "Remote",
            "location_type": "remote",
            "job_type": "full_time",
            "experience_level": "mid",
            "status": "open",
            **overrides,
        }

    cap("jobs.create", "POST", "/api/jobs/", json=job_payload(f"Contract Test Job {suffix}"))

    scratch = client.post("/api/jobs/", json=job_payload(f"Contract Scratch Job {suffix}"))
    db_session.expire_all()
    if scratch.status_code < 400:
        scratch_job_id = scratch.json()["id"]
        cap(
            "jobs.update",
            "PUT",
            f"/api/jobs/{scratch_job_id}",
            json=job_payload(
                f"Contract Test Job Renamed {suffix}",
                experience_level="senior",
                required_qualifications="Python, SQL",
            ),
        )
        cap("jobs.track_view", "POST", f"/api/jobs/{scratch_job_id}/track-view")
        cap("jobs.delete", "DELETE", f"/api/jobs/{scratch_job_id}")

    cap(
        "jobs.apply",
        "POST",
        f"/api/jobs/{seed['job_id']}/apply",
        json={"candidate_id": seed["candidate_ids"][1], "source": "direct"},
    )
    cap(
        "jobs.save",
        "POST",
        f"/api/jobs/{seed['job_ids'][1]}/save",
        json={"candidate_id": seed["candidate_ids"][1], "notes": "later"},
    )

    cap(
        "candidates.create",
        "POST",
        "/api/candidates/",
        json={
            "first_name": "Contract",
            "last_name": "Test",
            "email": f"contract-{suffix}@{SEED_EMAIL_DOMAIN}",
            "status": "active",
        },
    )

    scratch = client.post(
        "/api/candidates/",
        json={
            "first_name": "Contract",
            "last_name": "Delete",
            "email": f"contract-delete-{suffix}@{SEED_EMAIL_DOMAIN}",
            "status": "active",
        },
    )
    db_session.expire_all()
    if scratch.status_code < 400:
        cap("candidates.delete", "DELETE", f"/api/candidates/{scratch.json()['id']}")

    return captures


@pytest.fixture(scope="session")
def captures(read_captures, write_captures) -> dict:
    combined = {**read_captures, **write_captures}
    if UPDATING:
        _write_golden(combined)
    return combined


@pytest.fixture(scope="session")
def golden() -> dict:
    return _load_golden()


@pytest.mark.parametrize("case_id", READ_CASE_IDS)
def test_read_route_shape_unchanged(case_id, captures, golden):
    _assert_matches(case_id, captures, golden)


@pytest.mark.parametrize("case_id", WRITE_CASE_IDS)
def test_write_route_shape_unchanged(case_id, captures, golden):
    _assert_matches(case_id, captures, golden)


def _assert_matches(case_id: str, captures: dict, golden: dict) -> None:
    if UPDATING:
        pytest.skip("regenerating golden file")
    assert golden, (
        f"{GOLDEN_PATH} is missing. Generate it with "
        "UPDATE_API_GOLDEN=1 pytest backend/tests/test_api_contract.py"
    )
    assert case_id in golden, f"no golden entry for {case_id}; regenerate the golden file"
    assert case_id in captures, f"{case_id} was not exercised; the route setup failed"

    expected = golden[case_id]
    actual = captures[case_id]
    assert actual["status"] == expected["status"], (
        f"{case_id}: status changed {expected['status']} -> {actual['status']}"
    )
    assert actual["shape"] == expected["shape"], (
        f"{case_id}: response shape changed.\n"
        f"expected: {json.dumps(expected['shape'], indent=2, sort_keys=True)}\n"
        f"actual:   {json.dumps(actual['shape'], indent=2, sort_keys=True)}"
    )
