"""Authentication and read-only enforcement (Phase 3 spec §2, §8).

The load-bearing test here is `test_every_mutating_route_refuses_*`: instead of
listing routes by hand, it walks the application's own route table, so a write
endpoint added later is covered the moment it exists. That is the point of
installing the gate as an application-level dependency rather than sprinkling
`Depends` across fifteen router modules — there is no way to forget it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.main import app
from backend.tests.conftest import ADMIN_PASSWORD, SEED_EMAIL_DOMAIN
from backend.utils.auth import (
    MUTATING_METHODS,
    READ_ONLY_POST_PATHS,
    create_access_token,
    hash_password,
    verify_password,
)
from backend.utils.config import get_settings


def _mutating_routes():
    """Every (method, path) in the app that changes state, per the gate's rules."""
    seen = []
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        normalized = path.rstrip("/") or "/"
        if normalized in READ_ONLY_POST_PATHS:
            continue
        for method in sorted(methods & MUTATING_METHODS):
            seen.append((method, path))
    return seen


MUTATING_ROUTES = _mutating_routes()


def _concrete(path: str) -> str:
    """Fill path parameters with values that will never exist.

    The gate runs before the handler, so the target need not resolve — if a
    request gets far enough to 404 or 422, the gate already failed to stop it.
    """
    out = []
    for segment in path.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            out.append("999999" if "id" in segment.lower() else "x")
        else:
            out.append(segment)
    return "/".join(out)


# --- password hashing -------------------------------------------------------


def test_password_round_trips():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("Correct horse battery staple", hashed)


def test_verify_password_rejects_missing_and_malformed_hashes():
    assert not verify_password("anything", None)
    assert not verify_password("anything", "")
    assert not verify_password("anything", "not-a-bcrypt-hash")


# --- token issuance ---------------------------------------------------------


def test_demo_login_needs_no_credentials(client):
    response = client.post("/auth/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "demo"
    assert body["expires_in"] == get_settings().jwt_expiry_hours * 3600
    assert "hashed_password" not in body["user"]


def test_demo_login_is_idempotent(client):
    first = client.post("/auth/demo").json()
    second = client.post("/auth/demo").json()
    assert first["user"]["id"] == second["user"]["id"]


def test_login_with_valid_credentials(client, admin_user):
    response = client.post(
        "/auth/login", json={"email": admin_user.email, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


def test_login_with_wrong_password(client, admin_user):
    response = client.post(
        "/auth/login", json={"email": admin_user.email, "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_with_unknown_email_is_indistinguishable(client, admin_user):
    """No account enumeration: an unknown email must look like a bad password."""
    unknown = client.post(
        "/auth/login", json={"email": f"nobody@{SEED_EMAIL_DOMAIN}", "password": "wrong"}
    )
    wrong_password = client.post(
        "/auth/login", json={"email": admin_user.email, "password": "wrong"}
    )
    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json()


# --- token validation -------------------------------------------------------


def test_me_returns_the_authenticated_user(admin_client, admin_user):
    response = admin_client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == admin_user.email


def test_me_without_a_token(client):
    assert client.get("/auth/me").status_code == 401


@pytest.mark.parametrize(
    "header",
    ["", "Bearer", "Bearer ", "Basic abc", "Bearer not-a-jwt"],
    ids=["empty", "scheme-only", "scheme-and-space", "wrong-scheme", "garbage-token"],
)
def test_me_rejects_malformed_authorization_headers(client, header):
    assert client.get("/auth/me", headers={"Authorization": header}).status_code == 401


def test_me_rejects_an_expired_token(client, admin_user):
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": admin_user.id,
            "email": admin_user.email,
            "role": admin_user.role,
            "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


def test_me_rejects_a_token_signed_with_the_wrong_secret(client, admin_user):
    forged = jwt.encode(
        {"sub": admin_user.id, "role": "admin"}, "not-the-secret", algorithm="HS256"
    )
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_me_rejects_a_token_for_a_deleted_user(client, db_session):
    """A signed token is not enough; the subject still has to exist."""
    from backend.models.models import User

    ghost = User(email=f"ghost@{SEED_EMAIL_DOMAIN}", role="admin")
    db_session.add(ghost)
    db_session.flush()
    token = create_access_token(ghost)
    db_session.delete(ghost)
    db_session.flush()

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# --- the read-only gate -----------------------------------------------------


def test_the_route_table_actually_has_mutating_routes():
    """Guard against the enumeration below silently covering nothing."""
    assert len(MUTATING_ROUTES) > 20


@pytest.mark.parametrize(
    ("method", "path"), MUTATING_ROUTES, ids=[f"{m} {p}" for m, p in MUTATING_ROUTES]
)
def test_every_mutating_route_refuses_the_demo_role(demo_client, method, path):
    response = demo_client.request(method, _concrete(path))
    assert response.status_code == 403, (
        f"{method} {path} did not refuse a demo token (got {response.status_code})"
    )


@pytest.mark.parametrize(
    ("method", "path"), MUTATING_ROUTES, ids=[f"{m} {p}" for m, p in MUTATING_ROUTES]
)
def test_every_mutating_route_refuses_anonymous_callers(client, method, path):
    """/docs is public, so its "Try it out" button must not be a write channel."""
    response = client.request(method, _concrete(path))
    assert response.status_code == 401, (
        f"{method} {path} accepted an unauthenticated write (got {response.status_code})"
    )


@pytest.mark.parametrize("path", sorted(READ_ONLY_POST_PATHS))
def test_read_only_posts_are_reachable_by_the_demo_role(demo_client, path):
    """The allowlisted endpoints must not be caught by the gate.

    Asserting only "not 401/403" on purpose: several of these call a model or a
    matching agent, and this test is about the gate, not about them succeeding.
    """
    response = demo_client.post(path, json={})
    assert response.status_code not in (401, 403), f"{path} was blocked for the demo role"


@pytest.mark.parametrize("path", ["/api/resume/parse", "/api/resume/parse-direct"])
def test_resume_parse_refuses_to_save_for_the_demo_role(demo_client, path):
    """The allowlisted parse endpoints still must not write when asked to."""
    response = demo_client.post(
        path,
        files={"file": ("cv.txt", b"Ada Lovelace\nEngineer", "text/plain")},
        data={"save_to_db": "true"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/api/resume/parse", "/api/resume/parse-direct"])
def test_resume_parse_refuses_to_save_for_anonymous_callers(client, path):
    response = client.post(
        path,
        files={"file": ("cv.txt", b"Ada Lovelace\nEngineer", "text/plain")},
        data={"save_to_db": "true"},
    )
    assert response.status_code == 401


def test_admin_may_write(admin_client, seed):
    response = admin_client.post(f"/api/jobs/{seed['job_id']}/track-view")
    assert response.status_code == 200


def test_reads_stay_open_to_everyone(client, seed):
    assert client.get(f"/api/jobs/{seed['job_id']}").status_code == 200
