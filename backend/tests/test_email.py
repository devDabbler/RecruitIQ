"""Email templates, rendering, sending, and the log (ATS Phase E)."""
from __future__ import annotations

import smtplib
import uuid

import pytest

from backend.models.models import EmailLog, EmailTemplate
from backend.services import email_service
from backend.tests.phase_e_helpers import make_application, staff_client
from backend.utils.config import get_settings


# Generated per run: a fake credential, never a literal in the repository.
FAKE_SECRET = uuid.uuid4().hex


class FakeSMTP:
    """Stands in for smtplib.SMTP; records what would have been sent."""

    sent: list = []
    fail_with: Exception | None = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.tls = False
        self.user = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        self.user = user

    def send_message(self, message):
        if FakeSMTP.fail_with:
            raise FakeSMTP.fail_with
        FakeSMTP.sent.append((self, message))


@pytest.fixture
def smtp(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_from", "Hiring <hiring@example.test>")
    monkeypatch.setattr(settings, "smtp_username", "mailer")
    monkeypatch.setattr(settings, "smtp_password", FAKE_SECRET)
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    FakeSMTP.fail_with = None
    return settings


@pytest.fixture
def no_smtp(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_from", "")
    return settings


# --- service ---------------------------------------------------------------


def test_render_fills_known_placeholders():
    text, missing = email_service.render(
        "Hi {{candidate_first_name}}, about {{ job_title }}.",
        {"candidate_first_name": "Mira", "job_title": "Platform Engineer"},
    )
    assert text == "Hi Mira, about Platform Engineer."
    assert missing == []


def test_render_reports_missing_and_unknown_placeholders():
    text, missing = email_service.render(
        "Link: {{status_link}} {{status_link}} {{favourite_color}}",
        {"status_link": None},
    )
    assert text == "Link: {{status_link}} {{status_link}} {{favourite_color}}"
    assert missing == ["status_link", "favourite_color"]


def test_unknown_placeholders():
    assert email_service.unknown_placeholders("{{job_title}} {{salary}} {{salary}}") == ["salary"]


def test_send_uses_starttls_and_login_when_configured(smtp):
    email_service.send(smtp, "mira@example.test", "Hello", "Body text")
    connection, message = FakeSMTP.sent[0]
    assert connection.host == "smtp.example.test" and connection.tls and connection.user == "mailer"
    assert message["To"] == "mira@example.test"
    assert message["From"] == "Hiring <hiring@example.test>"
    assert message.get_content().strip() == "Body text"


def test_send_without_transport_raises(no_smtp):
    assert email_service.transport_configured(no_smtp) is False
    with pytest.raises(email_service.EmailTransportError, match="No email transport"):
        email_service.send(no_smtp, "mira@example.test", "Hello", "Body")


def test_send_strips_header_injection_and_hides_the_password(smtp):
    email_service.send(smtp, "mira@example.test", "Hello\r\nBcc: someone@example.test", "Body")
    _, message = FakeSMTP.sent[0]
    assert "\n" not in message["Subject"] and message["Bcc"] is None

    FakeSMTP.fail_with = smtplib.SMTPAuthenticationError(535, f"rejected {FAKE_SECRET}".encode())
    with pytest.raises(email_service.EmailTransportError) as excinfo:
        email_service.send(smtp, "mira@example.test", "Hello", "Body")
    assert FAKE_SECRET not in str(excinfo.value)


# --- routes ----------------------------------------------------------------

PREVIEW = "/api/applications/{id}/emails/preview?template_key=interview_invite"


def _send_body(mode="send", **overrides):
    body = {
        "template_key": "interview_invite",
        "subject": "Next step for the {{job_title}} role",
        "body": "Hi {{candidate_first_name}}, more soon. {{sender_name}}",
        "mode": mode,
    }
    body.update(overrides)
    return body


def test_templates_list_has_the_four_defaults(client, no_smtp):
    response = client.get("/api/email-templates")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [t["key"] for t in body["templates"]] == [
        "interview_invite",
        "resume_request",
        "polite_close",
        "offer",
    ]
    assert body["transport_configured"] is False
    assert "status_link" in body["placeholders"]


def test_default_templates_have_no_dashes_or_unknown_placeholders(db_session):
    for template in db_session.query(EmailTemplate).all():
        text = f"{template.subject}\n{template.body}"
        assert "—" not in text and "–" not in text
        assert email_service.unknown_placeholders(text) == []


def test_preview_as_demo_fills_first_name_and_flags_the_missing_link(demo_client, db_session):
    _, application = make_application(db_session)
    response = demo_client.get(PREVIEW.format(id=application.id))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"].startswith("Hi Mira,")
    assert body["missing"] == ["status_link"]
    assert body["to_address"].startswith("mira-")


def test_preview_includes_the_status_link_once_issued(admin_client, db_session):
    _, application = make_application(db_session)
    path = admin_client.post(f"/api/applications/{application.id}/status-link").json()["path"]
    body = admin_client.get(PREVIEW.format(id=application.id)).json()
    assert body["missing"] == []
    assert f"{get_settings().public_app_url.rstrip('/')}{path}" in body["body"]


def test_send_permissions(demo_client, db_session, override_get_db):
    _, application = make_application(db_session)
    url = f"/api/applications/{application.id}/emails"
    assert demo_client.post(url, json=_send_body("copied")).status_code == 403
    interviewer = staff_client(db_session, "interviewer")
    assert interviewer.post(url, json=_send_body("copied")).status_code == 403
    # Phase B's interviewer gate refuses paths outside INTERVIEWER_PATHS with 403
    # before the handler runs; email previews are not on that list.
    assert interviewer.get(PREVIEW.format(id=application.id)).status_code == 403


def test_copy_mode_logs_without_sending(db_session, override_get_db, smtp):
    _, application = make_application(db_session)
    team = staff_client(db_session, "hiring_team")
    response = team.post(f"/api/applications/{application.id}/emails", json=_send_body("copied"))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "copied"
    assert response.json()["sent_by_name"] == "Test Hiring Team"
    assert FakeSMTP.sent == []


def test_send_without_transport_is_409(admin_client, db_session, no_smtp):
    _, application = make_application(db_session)
    response = admin_client.post(f"/api/applications/{application.id}/emails", json=_send_body())
    assert response.status_code == 409
    assert "Copy the text" in response.json()["detail"]


def test_send_with_transport_logs_sent(admin_client, db_session, smtp):
    _, application = make_application(db_session)
    response = admin_client.post(f"/api/applications/{application.id}/emails", json=_send_body())
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "sent"
    _, message = FakeSMTP.sent[0]
    assert message["Subject"] == "Next step for the Platform Engineer role"
    log = admin_client.get(f"/api/applications/{application.id}/emails").json()
    assert [entry["status"] for entry in log] == ["sent"]


def test_send_failure_logs_failed_and_returns_502(admin_client, db_session, smtp):
    _, application = make_application(db_session)
    FakeSMTP.fail_with = smtplib.SMTPServerDisconnected("gone")
    response = admin_client.post(f"/api/applications/{application.id}/emails", json=_send_body())
    assert response.status_code == 502
    entry = db_session.query(EmailLog).filter(EmailLog.application_id == application.id).one()
    assert entry.status == "failed" and "SMTPServerDisconnected" in entry.error


def test_send_refuses_unfilled_placeholders(admin_client, db_session, smtp):
    _, application = make_application(db_session)
    response = admin_client.post(
        f"/api/applications/{application.id}/emails",
        json=_send_body(body="Track it here: {{status_link}}"),
    )
    assert response.status_code == 409
    assert "{{status_link}}" in response.json()["detail"]
    assert FakeSMTP.sent == []


def test_update_template_permissions_and_validation(db_session, override_get_db):
    template = db_session.query(EmailTemplate).filter(EmailTemplate.key == "offer").one()
    original = (template.name, template.subject, template.body)
    url = "/api/email-templates/offer"
    edit = {"name": "Offer", "subject": "Offer: {{job_title}}", "body": "Hi {{candidate_first_name}}"}
    try:
        assert staff_client(db_session, "hiring_team").put(url, json=edit).status_code == 403
        manager = staff_client(db_session, "hiring_manager")
        bad = manager.put(url, json={**edit, "body": "Hi {{nickname}}"})
        assert bad.status_code == 400 and "{{nickname}}" in bad.json()["detail"]
        good = manager.put(url, json=edit)
        assert good.status_code == 200, good.text
        assert good.json()["subject"] == "Offer: {{job_title}}"
    finally:
        template.name, template.subject, template.body = original
        db_session.commit()
