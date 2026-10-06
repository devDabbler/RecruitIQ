"""feedback drafts and feedback templates

Track 2 Phase 4. `feedback.status` is `draft` or `submitted`; every row that
exists today was submitted, so the server default backfills them. A draft
may be partial, so rating and recommendation become nullable and
`submitted_at` is NULL until submit; a check constraint keeps a submitted
row complete. `updated_at` (backfilled from `submitted_at`) is when the
author last touched it, which is what retention reads.

`feedback_templates` holds starting text for the notes box: global when
`job_id` is NULL, else for one job. Not candidate data.

Revision ID: d4a7e9b1c3f5
Revises: b1d4f6a8c2e3
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a7e9b1c3f5"
down_revision: Union[str, None] = "b1d4f6a8c2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feedback",
        sa.Column("status", sa.String(length=10), nullable=False, server_default="submitted"),
    )
    op.add_column("feedback", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE feedback SET updated_at = submitted_at")
    op.alter_column("feedback", "updated_at", nullable=False, server_default=sa.func.now())
    op.alter_column("feedback", "rating", nullable=True)
    op.alter_column("feedback", "recommendation", nullable=True)
    # The server default stays: a raw INSERT of finished feedback still gets a
    # time. Drafts write NULL explicitly.
    op.alter_column("feedback", "submitted_at", nullable=True)
    op.create_check_constraint("ck_feedback_status", "feedback", "status IN ('draft', 'submitted')")
    op.create_check_constraint(
        "ck_feedback_submitted_complete",
        "feedback",
        "status = 'draft' OR (rating IS NOT NULL AND recommendation IS NOT NULL AND submitted_at IS NOT NULL)",
    )

    op.create_table(
        "feedback_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_feedback_templates_job_id", "feedback_templates", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_feedback_templates_job_id", table_name="feedback_templates")
    op.drop_table("feedback_templates")
    op.execute("DELETE FROM feedback WHERE status = 'draft'")
    op.drop_constraint("ck_feedback_submitted_complete", "feedback", type_="check")
    op.drop_constraint("ck_feedback_status", "feedback", type_="check")
    op.alter_column("feedback", "submitted_at", nullable=False)
    op.alter_column("feedback", "recommendation", nullable=False)
    op.alter_column("feedback", "rating", nullable=False)
    op.drop_column("feedback", "updated_at")
    op.drop_column("feedback", "status")
