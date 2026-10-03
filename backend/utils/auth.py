"""Authentication primitives: password hashing, JWTs, and the read-only gate.

Phase 3 spec §2. Deliberately small — two roles, one token type, no refresh
rotation. The one piece that carries real weight is `enforce_read_only`, which
is installed as an application-level dependency in `backend/main.py` so it runs
on every request whether or not a route author remembered it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.models.models import User
from backend.utils.config import get_settings
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

ROLE_ADMIN = "admin"
ROLE_HIRING_MANAGER = "hiring_manager"
ROLE_HIRING_TEAM = "hiring_team"
ROLE_INTERVIEWER = "interviewer"
ROLE_DEMO = "demo"

# ATS Phase B: the four roles a person on the team can hold. `demo` is the
# public read-only account and is never a staff role.
STAFF_ROLES = (ROLE_ADMIN, ROLE_HIRING_MANAGER, ROLE_HIRING_TEAM, ROLE_INTERVIEWER)

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Paths that use a mutating verb but do not mutate anything: authentication
# itself, and the read-heavy endpoints that take a request body because their
# input does not fit in a query string. Everything not listed here is blocked
# for the demo role, so a route added later is denied by default rather than
# quietly exposed.
READ_ONLY_POST_PATHS = frozenset(
    {
        "/auth/login",
        "/auth/demo",
        "/api/assistant/chat",
        "/api/assistant/chat/stream",
        "/api/search/match_candidates",
        "/api/search/match_jobs",
        "/api/search/match_report",
        "/api/enhanced-matching/match-jobs",
        "/api/enhanced-matching/match-candidates",
        "/api/enhanced-matching/similar-jobs",
        # Parsing a resume is a pure read *provided* save_to_db stays false;
        # the handlers enforce that for demo callers themselves, since a
        # path-based gate cannot see a multipart form field.
        "/api/resume/parse",
        "/api/resume/parse-direct",
    }
)

# bcrypt silently ignores anything past 72 bytes; truncate explicitly so a long
# password cannot be confused with a shorter prefix of itself.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode(
        "utf-8"
    )


def verify_password(password: str, hashed: Optional[str]) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:_BCRYPT_MAX_BYTES], hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash in the database — treat as a failed login, not a 500.
        logger.warning("Rejected a login against a malformed password hash")
        return False


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.jwt_expiry_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Return the token's claims, or raise 401 for anything untrustworthy."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the bearer token to a User row, or 401."""
    token = bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_access_token(token)
    user = db.query(User).filter(User.id == claims.get("sub")).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Like `get_current_user`, but returns None instead of 401 when anonymous."""
    if not bearer_token(request):
        return None
    return get_current_user(request, db)


def current_role(request: Request) -> Optional[str]:
    """Read the role claim without a database round trip.

    Used by the request-scoped gate, which runs on every call and should not add
    a query to each one. The claim is signed, so trusting it here is safe; the
    routes that need the row still use `get_current_user`.
    """
    token = bearer_token(request)
    if not token:
        return None
    try:
        return decode_access_token(token).get("role")
    except HTTPException:
        # An unreadable token is not a role. Whether that is fatal is the
        # route's business, not the gate's.
        return None


def request_identity(request: Request, db: Session) -> tuple[Optional[str], Optional[User]]:
    """(role, user) for this request, read from the database.

    The token's role claim is what was true when it was issued; a role change
    or a deleted account must take effect on the next request, not when a
    24-hour token expires. Demo tokens skip the lookup: the demo role cannot
    change and the public demo is most of the traffic, so `user` is None for
    them. An unreadable token counts as anonymous here; whether that is fatal
    is the route's business. Cached on `request.state` so both app-wide gates
    and the handlers share one query.
    """
    cached = getattr(request.state, "identity", None)
    if cached is not None:
        return cached

    identity: tuple[Optional[str], Optional[User]] = (None, None)
    token = bearer_token(request)
    if token:
        try:
            claims = decode_access_token(token)
        except HTTPException:
            claims = None
        if claims is not None:
            if claims.get("role") == ROLE_DEMO:
                identity = (ROLE_DEMO, None)
            else:
                user = db.query(User).filter(User.id == claims.get("sub")).first()
                if user is not None:
                    identity = (user.role, user)
    request.state.identity = identity
    return identity


def enforce_read_only(request: Request, db: Session = Depends(get_db)) -> None:
    """Writes need a role that the permission table grants. Installed app-wide.

    The UI also hides mutating controls, but a hidden button is not an access
    control: anyone can POST straight at the API. This is the gate; the UI is
    courtesy (spec section 2).

    Anonymous callers are refused (401), not just the demo role (403). `/docs`
    is deliberately public, and Swagger UI's "Try it out" sends requests with
    no Authorization header at all.

    ATS Phase B: admin may write anything. The other staff roles may write
    only where `ROUTE_PERMISSIONS` grants them; a route missing from that
    table is admin-only, so a forgotten route is denied rather than exposed.
    """
    if request.method not in MUTATING_METHODS:
        return
    path = request.url.path.rstrip("/") or "/"
    if path in READ_ONLY_POST_PATHS:
        return

    role, _ = request_identity(request, db)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to modify data",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if role == ROLE_ADMIN:
        return
    if role == ROLE_DEMO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This is a read-only demo account. Sign in as an administrator to "
                "change data."
            ),
        )

    # Imported here: permissions imports this module for the role constants.
    from backend.utils.permissions import can, role_label, route_permission

    permission = route_permission(request.method, path)
    if permission is not None and can(role, permission):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Your role ({role_label(role)}) cannot make this change. "
            "Ask an administrator if you need it."
        ),
    )


def require_write_access(user: User = Depends(get_current_user)) -> User:
    """For routes that want an explicit, authenticated writer."""
    if user.role == ROLE_DEMO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is a read-only demo account.",
        )
    return user


def get_or_create_demo_user(db: Session) -> User:
    settings = get_settings()
    user = db.query(User).filter(User.email == settings.demo_user_email).first()
    if user:
        return user
    user = User(email=settings.demo_user_email, hashed_password=None, role=ROLE_DEMO)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created the demo user %s", settings.demo_user_email)
    return user
