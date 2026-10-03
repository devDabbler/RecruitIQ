"""public status links and email templates/log

ATS Phase E (spec 2026-10-03 sections 3.1, 3.2, 8). Adds a revocable
public_token to job_applications for the candidate status page, the
email_templates table seeded with four editable defaults, and email_log,
which records every email sent or copied from the app.

The default template text lives here rather than in seed_demo.py because
it is product configuration, not demo data: production needs it without
a reseed. It is synthetic and contains no addresses.

Revision ID: f7b1d4e5a6c7
Revises: e6a0c3d4f5b6
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7b1d4e5a6c7"
down_revision: Union[str, None] = "e6a0c3d4f5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TEMPLATES = [
    (
        "interview_invite",
        "Interview invitation",
        "Next step for the {{job_title}} role",
        "Hi {{candidate_first_name}},\n\n"
        "Thank you for your interest in the {{job_title}} role on our {{department}} team. "
        "We would like to invite you to the next stage of our process.\n\n"
        "Please reply with a few times that work for you over the next week, and we will confirm one.\n\n"
        "You can follow your application at any time here: {{status_link}}\n\n"
        "Best regards,\n{{sender_name}}",
    ),
    (
        "resume_request",
        "Resume request",
        "Your application for {{job_title}}",
        "Hi {{candidate_first_name}},\n\n"
        "Thank you for applying for the {{job_title}} role. Could you reply with an up-to-date copy "
        "of your resume? We want to make sure we are reviewing your most recent experience.\n\n"
        "Best regards,\n{{sender_name}}",
    ),
    (
        "polite_close",
        "Polite close",
        "An update on your {{job_title}} application",
        "Hi {{candidate_first_name}},\n\n"
        "Thank you for the time you have spent with us on the {{job_title}} role. After careful "
        "consideration, we have decided not to move forward with your application.\n\n"
        "We appreciate your interest in joining the {{department}} team and wish you the best in "
        "your search.\n\n"
        "Kind regards,\n{{sender_name}}",
    ),
    (
        "offer",
        "Offer",
        "Offer for the {{job_title}} role",
        "Hi {{candidate_first_name}},\n\n"
        "We are delighted to let you know that we would like to offer you the {{job_title}} role "
        "on our {{department}} team. A formal offer letter with the details will follow shortly.\n\n"
        "If you have any questions in the meantime, just reply to this email.\n\n"
        "Congratulations,\n{{sender_name}}",
    ),
]


def upgrade() -> None:
    op.add_column("job_applications", sa.Column("public_token", sa.String(36), nullable=True))
    op.add_column("job_applications", sa.Column("public_token_created_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_job_applications_public_token", "job_applications", ["public_token"], unique=True
    )

    templates = op.create_table(
        "email_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.bulk_insert(
        templates,
        [
            {"key": key, "name": name, "subject": subject, "body": body}
            for key, name, subject, body in DEFAULT_TEMPLATES
        ],
    )

    op.create_table(
        "email_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("job_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_key", sa.String(50), nullable=True),
        sa.Column("to_address", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_email_log_application_id", "email_log", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_email_log_application_id", table_name="email_log")
    op.drop_table("email_log")
    op.drop_table("email_templates")
    op.drop_index("ix_job_applications_public_token", table_name="job_applications")
    op.drop_column("job_applications", "public_token_created_at")
    op.drop_column("job_applications", "public_token")
