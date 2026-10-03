"""Email templates and the SMTP transport (ATS Phase E).

Templates hold `{{placeholder}}` markers from a fixed list. Rendering fills
the ones it has values for and reports the rest as missing, and the send
route refuses to send while anything is missing, so a candidate never gets
an email with a literal "{{status_link}}" in it.

The transport is plain SMTP with STARTTLS, configured from the environment.
When it is not configured, nothing is sent and the UI offers the text to
copy instead; that is a supported state, not an error.
"""
from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.models import Candidate, Job, JobApplication, User

PLACEHOLDERS = ("candidate_first_name", "job_title", "department", "sender_name", "status_link")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_]+)\s*\}\}")
DEFAULT_SENDER_NAME = "The hiring team"


class EmailTransportError(Exception):
    """Sending failed or is not configured. The message is safe to show a user."""


def render(text: str, values: dict[str, Optional[str]]) -> tuple[str, list[str]]:
    """Fill known placeholders that have a value. Return the text and what is still missing."""
    missing: list[str] = []

    def substitute(match: re.Match) -> str:
        name = match.group(1)
        value = values.get(name) if name in PLACEHOLDERS else None
        if value:
            return value
        if name not in missing:
            missing.append(name)
        return match.group(0)

    return _PLACEHOLDER_RE.sub(substitute, text or ""), missing


def unknown_placeholders(text: str) -> list[str]:
    found: list[str] = []
    for name in _PLACEHOLDER_RE.findall(text or ""):
        if name not in PLACEHOLDERS and name not in found:
            found.append(name)
    return found


def placeholder_values(
    db: Session, application: JobApplication, sender: Optional[User], settings
) -> dict[str, Optional[str]]:
    candidate = db.get(Candidate, application.candidate_id)
    job = db.get(Job, application.job_id)
    link = None
    if application.public_token:
        link = f"{settings.public_app_url.rstrip('/')}/c/{application.public_token}"
    sender_name = (getattr(sender, "name", None) or "").strip() or DEFAULT_SENDER_NAME
    first_name = (candidate.first_name or "").strip() if candidate else ""
    return {
        "candidate_first_name": first_name or None,
        "job_title": job.title if job else None,
        "department": job.department if job else None,
        "sender_name": sender_name,
        "status_link": link,
    }


def transport_configured(settings) -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def send(settings, to_address: str, subject: str, body: str) -> None:
    if not transport_configured(settings):
        raise EmailTransportError("No email transport is configured.")
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_address
    # A newline in a header is how one email becomes two recipients.
    message["Subject"] = " ".join(subject.splitlines()).strip()
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # The class name only: server replies can echo credentials back.
        raise EmailTransportError(
            f"The mail server did not accept the message ({exc.__class__.__name__})."
        ) from exc
