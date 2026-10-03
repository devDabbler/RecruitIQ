"""Email templates, preview, send, and the log (ATS Phase E).

Preview and the log are reads, open to anyone who can see the candidate
(including the demo, so the portfolio shows the feature). Sending and
logging a copy need PIPELINE_MOVE; editing templates needs
TEMPLATES_MANAGE. Plain `def` handlers.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..models.email import (
    EmailLogOut,
    EmailPreview,
    EmailSendRequest,
    EmailTemplateOut,
    EmailTemplatesResponse,
    EmailTemplateUpdate,
)
from ..models.models import Candidate, EmailLog, EmailTemplate, User
from ..services import email_service
from ..utils.auth import get_optional_user
from ..utils.config import get_settings
from ..utils.database import get_db
from ..utils.permissions import PIPELINE_MOVE, TEMPLATES_MANAGE, require
from .application_access import visible_application_or_404

router = APIRouter()


def _braced(names: List[str]) -> str:
    return ", ".join("{{" + name + "}}" for name in names)


def _log_out(db: Session, entry: EmailLog) -> EmailLogOut:
    sender = db.get(User, entry.sent_by) if entry.sent_by else None
    return EmailLogOut(
        id=entry.id,
        template_key=entry.template_key,
        to_address=entry.to_address,
        subject=entry.subject,
        body=entry.body,
        status=entry.status,
        error=entry.error,
        sent_by_name=(getattr(sender, "name", None) or None) if sender else None,
        created_at=entry.created_at,
    )


@router.get("/email-templates", response_model=EmailTemplatesResponse)
def list_templates(db: Session = Depends(get_db)) -> EmailTemplatesResponse:
    templates = db.query(EmailTemplate).order_by(EmailTemplate.id).all()
    return EmailTemplatesResponse(
        templates=[EmailTemplateOut.model_validate(t) for t in templates],
        transport_configured=email_service.transport_configured(get_settings()),
        placeholders=list(email_service.PLACEHOLDERS),
    )


@router.put("/email-templates/{key}", response_model=EmailTemplateOut)
def update_template(
    key: str,
    payload: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require(TEMPLATES_MANAGE)),
) -> EmailTemplateOut:
    template = db.query(EmailTemplate).filter(EmailTemplate.key == key).first()
    if template is None:
        raise HTTPException(status_code=404, detail=f"No email template named '{key}'.")
    unknown = email_service.unknown_placeholders(payload.subject + "\n" + payload.body)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown placeholder {_braced(unknown[:1])}. Use one of: "
            f"{_braced(list(email_service.PLACEHOLDERS))}.",
        )
    template.name = payload.name.strip()
    template.subject = payload.subject.strip()
    template.body = payload.body.strip()
    template.updated_at = datetime.utcnow()
    template.updated_by = user.id
    db.commit()
    db.refresh(template)
    return EmailTemplateOut.model_validate(template)


@router.get("/applications/{application_id}/emails/preview", response_model=EmailPreview)
def preview_email(
    application_id: int,
    template_key: str = Query(..., pattern=r"^[a-z_]{1,50}$"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> EmailPreview:
    application = visible_application_or_404(db, application_id, user)
    template = db.query(EmailTemplate).filter(EmailTemplate.key == template_key).first()
    if template is None:
        raise HTTPException(status_code=404, detail=f"No email template named '{template_key}'.")
    settings = get_settings()
    values = email_service.placeholder_values(db, application, user, settings)
    subject, missing_subject = email_service.render(template.subject, values)
    body, missing_body = email_service.render(template.body, values)
    candidate = db.get(Candidate, application.candidate_id)
    return EmailPreview(
        template_key=template.key,
        subject=subject,
        body=body,
        to_address=candidate.email if candidate else None,
        missing=list(dict.fromkeys(missing_subject + missing_body)),
        transport_configured=email_service.transport_configured(settings),
    )


@router.get("/applications/{application_id}/emails", response_model=List[EmailLogOut])
def list_emails(
    application_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> List[EmailLogOut]:
    application = visible_application_or_404(db, application_id, user)
    entries = (
        db.query(EmailLog)
        .filter(EmailLog.application_id == application.id)
        .order_by(EmailLog.created_at.desc(), EmailLog.id.desc())
        .all()
    )
    return [_log_out(db, entry) for entry in entries]


@router.post("/applications/{application_id}/emails", response_model=EmailLogOut)
def send_email(
    application_id: int,
    payload: EmailSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require(PIPELINE_MOVE)),
) -> EmailLogOut:
    """Send through SMTP, or log that the text was copied to send by hand."""
    application = visible_application_or_404(db, application_id, user)
    candidate = db.get(Candidate, application.candidate_id)
    if candidate is None or not candidate.email:
        raise HTTPException(status_code=409, detail="This candidate has no email address on file.")

    settings = get_settings()
    values = email_service.placeholder_values(db, application, user, settings)
    subject, missing_subject = email_service.render(payload.subject, values)
    body, missing_body = email_service.render(payload.body, values)
    missing = list(dict.fromkeys(missing_subject + missing_body))
    if missing:
        hint = (
            " Create a status link first, or remove {{status_link}} from the text."
            if "status_link" in missing
            else ""
        )
        raise HTTPException(status_code=409, detail=f"Fill in {_braced(missing)} before sending.{hint}")

    entry = EmailLog(
        application_id=application.id,
        template_key=payload.template_key,
        to_address=candidate.email,
        subject=subject,
        body=body,
        status="copied",
        sent_by=user.id,
        created_at=datetime.utcnow(),
    )
    if payload.mode == "send":
        if not email_service.transport_configured(settings):
            raise HTTPException(
                status_code=409,
                detail="No mail server is configured. Copy the text and send it from your own inbox.",
            )
        try:
            email_service.send(settings, candidate.email, subject, body)
            entry.status = "sent"
        except email_service.EmailTransportError as exc:
            entry.status = "failed"
            entry.error = str(exc)
            db.add(entry)
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _log_out(db, entry)
