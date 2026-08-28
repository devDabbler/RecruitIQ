"""Pydantic schemas for authentication (Phase 3 spec §2).

The SQLAlchemy `User` model lives in `models/models.py` alongside the rest of
the ORM so it registers against the same `Base`.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

Role = Literal["admin", "demo"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: Role
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds
    user: UserResponse
