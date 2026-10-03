"""Request and response shapes for the email router (ATS Phase E)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EmailTemplateOut(BaseModel):
    key: str
    name: str
    subject: str
    body: str
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EmailTemplatesResponse(BaseModel):
    templates: List[EmailTemplateOut]
    transport_configured: bool
    placeholders: List[str]


class EmailTemplateUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)


class EmailPreview(BaseModel):
    template_key: str
    subject: str
    body: str
    to_address: Optional[str] = None
    missing: List[str]
    transport_configured: bool


class EmailSendRequest(BaseModel):
    template_key: Optional[str] = Field(default=None, max_length=50)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    # "copied": the user copied the text to send from their own inbox; logged, not sent.
    mode: Literal["send", "copied"]


class EmailLogOut(BaseModel):
    id: int
    template_key: Optional[str] = None
    to_address: str
    subject: str
    body: str
    status: str
    error: Optional[str] = None
    sent_by_name: Optional[str] = None
    created_at: datetime
