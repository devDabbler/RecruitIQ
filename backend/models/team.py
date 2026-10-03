"""Request and response shapes for the team router (ATS Phase B)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

StaffRole = Literal["admin", "hiring_manager", "hiring_team", "interviewer"]


class MessageOut(BaseModel):
    message: str


class TeamMember(BaseModel):
    id: str
    # Omitted (null) for viewers who cannot invite people: the demo can see
    # the team page, and a real administrator's address must not be public.
    email: Optional[str] = None
    name: Optional[str] = None
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamListResponse(BaseModel):
    members: List[TeamMember]


class InviteRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    role: StaffRole


class InviteResponse(BaseModel):
    member: TeamMember
    temporary_password: str


class RoleChangeRequest(BaseModel):
    role: StaffRole


class ProfileResponse(TeamMember):
    timezone: Optional[str] = None


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    timezone: Optional[str] = Field(default=None, max_length=64)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12, max_length=128)
