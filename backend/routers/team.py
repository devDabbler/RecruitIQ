"""The team, invitations, and each person's own settings (ATS Phase B).

No email is sent in Phase B: an invite creates the account with a temporary
password that is returned once and shown once, and the inviter passes it on.
Plain `def` handlers (sync ORM).
"""
from __future__ import annotations

import re
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..models.models import ApplicationStage, Feedback, Interview, User
from ..models.team import (
    InviteRequest,
    InviteResponse,
    MessageOut,
    PasswordChange,
    ProfileResponse,
    ProfileUpdate,
    RoleChangeRequest,
    TeamListResponse,
    TeamMember,
)
from ..services.feedback_service import display_name
from ..utils.auth import (
    ROLE_ADMIN,
    ROLE_DEMO,
    STAFF_ROLES,
    get_current_user,
    hash_password,
    request_identity,
    verify_password,
)
from ..utils.database import get_db
from ..utils.permissions import DELETE_RECORDS, USERS_CHANGE_ROLE, USERS_INVITE, can, require

router = APIRouter(prefix="/team")

# IANA-style names such as America/Chicago or UTC. The web offers a fixed list.
TIMEZONE_RE = re.compile(r"^[A-Za-z_]+(/[A-Za-z0-9_+\-]+)*$")


def _member(user: User, show_email: bool) -> TeamMember:
    member = TeamMember.model_validate(user)
    if not show_email:
        member.email = None
    return member


def _staff_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None or user.role == ROLE_DEMO:
        raise HTTPException(status_code=404, detail="No one on the team has that id.")
    return user


@router.get("/users", response_model=TeamListResponse)
def list_team(request: Request, db: Session = Depends(get_db)) -> TeamListResponse:
    role, _ = request_identity(request, db)
    show_email = can(role, USERS_INVITE)
    people = db.query(User).filter(User.role.in_(STAFF_ROLES)).all()
    order = {r: i for i, r in enumerate(STAFF_ROLES)}
    people.sort(key=lambda u: (order.get(u.role, 9), (u.name or u.email).lower()))
    return TeamListResponse(members=[_member(u, show_email) for u in people])


@router.post("/users", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def invite(
    payload: InviteRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require(USERS_INVITE)),
) -> InviteResponse:
    if payload.role == ROLE_ADMIN and actor.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Only an administrator can add another administrator.")
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="Someone with that email is already on the team.")
    temporary = secrets.token_urlsafe(12)  # 16 characters
    user = User(email=email, name=payload.name.strip(), role=payload.role, hashed_password=hash_password(temporary))
    db.add(user)
    db.commit()
    db.refresh(user)
    return InviteResponse(member=_member(user, True), temporary_password=temporary)


@router.put("/users/{user_id}/role", response_model=TeamMember)
def change_role(
    user_id: str,
    payload: RoleChangeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require(USERS_CHANGE_ROLE)),
) -> TeamMember:
    user = _staff_or_404(db, user_id)
    if user.id == actor.id:
        # Also what keeps the last administrator from demoting themselves.
        raise HTTPException(status_code=409, detail="You cannot change your own role.")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return _member(user, True)


@router.delete("/users/{user_id}", response_model=MessageOut)
def remove(
    user_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(DELETE_RECORDS)),
) -> MessageOut:
    user = _staff_or_404(db, user_id)
    if user.id == actor.id:
        raise HTTPException(status_code=409, detail="You cannot remove yourself.")
    has_feedback = (
        db.query(Feedback.id)
        .join(Interview, Feedback.interview_id == Interview.id)
        .filter(Interview.interviewer_id == user.id)
        .first()
    )
    if has_feedback is not None:
        raise HTTPException(
            status_code=409,
            detail=f"{display_name(user)} has submitted feedback, which stays on the record. Change their role instead.",
        )
    name = display_name(user)
    db.query(Interview).filter(Interview.interviewer_id == user.id).delete(synchronize_session=False)
    db.query(ApplicationStage).filter(ApplicationStage.changed_by == user.id).update(
        {ApplicationStage.changed_by: None}, synchronize_session=False
    )
    # stage_default_interviewers rows go by ON DELETE CASCADE; jobs'
    # hiring_manager_id and recruiter_id become NULL by ON DELETE SET NULL.
    db.delete(user)
    db.commit()
    return MessageOut(message=f"Removed {name} from the team.")


@router.get("/me", response_model=ProfileResponse)
def my_profile(user: User = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse.model_validate(user)


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileResponse:
    timezone: Optional[str] = (payload.timezone or "").strip() or None
    if timezone is not None and not TIMEZONE_RE.fullmatch(timezone):
        raise HTTPException(status_code=422, detail="Choose a time zone from the list.")
    user.name = payload.name.strip()
    user.timezone = timezone
    db.commit()
    db.refresh(user)
    return ProfileResponse.model_validate(user)


@router.put("/me/password", response_model=MessageOut)
def change_my_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageOut:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Your current password is not correct.")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return MessageOut(message="Password changed.")
