"""Authentication routes (Phase 3 spec §2).

Three endpoints, no registration: this is a portfolio demo, and the visitor
following a link from a resume should land in a working product rather than a
signup form. `POST /auth/demo` is what the Next.js middleware calls on a
cookie-less request; it issues a read-only token and the visitor never sees a
login screen.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..models.models import User
from ..models.user import LoginRequest, TokenResponse, UserResponse
from ..utils.auth import (
    create_access_token,
    get_current_user,
    get_or_create_demo_user,
    verify_password,
)
from ..utils.config import get_settings
from ..utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=get_settings().jwt_expiry_hours * 3600,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange email and password for a bearer token."""
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        # One message for both cases: a distinct "no such user" reply would let
        # anyone enumerate accounts.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info("Login succeeded for %s (%s)", user.email, user.role)
    return _token_response(user)


@router.post("/demo", response_model=TokenResponse)
def demo_login(db: Session = Depends(get_db)) -> TokenResponse:
    """Issue a read-only token with no credentials.

    Safe to call from anywhere: the token's `demo` role is refused by
    `enforce_read_only` on every mutating route.
    """
    return _token_response(get_or_create_demo_user(db))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)
