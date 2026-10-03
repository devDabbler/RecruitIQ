"""notes and candidate_tags, importing the old candidates.notes text

ATS Phase C (spec 2026-10-03 section 3.1). Creates both tables, then copies
every non-empty candidates.notes value into a candidate-level note with no
author, which the UI shows as "Earlier note". candidates.notes itself is left
untouched: the spec makes it read-only now and drops it one release later,
and leaving it in place makes the downgrade lossless.

Revision ID: e6a0c3d4f5b6
Revises: d5f9b2c3e4a5
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6a0c3d4f5b6"
down_revision: Union[str, None] = "d5f9b2c3e4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("job_applications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "stage_id",
            sa.Integer(),
            sa.ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notes_candidate_id", "notes", ["candidate_id"])
    op.create_index("ix_notes_application_id", "notes", ["application_id"])

    op.create_table(
        "candidate_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("candidate_id", "tag", name="uq_candidate_tag"),
    )
    op.create_index("ix_candidate_tags_candidate_id", "candidate_tags", ["candidate_id"])
    op.create_index("ix_candidate_tags_tag", "candidate_tags", ["tag"])

    op.execute(
        "INSERT INTO notes (candidate_id, body, created_at) "
        "SELECT id, btrim(notes), COALESCE(updated_at, created_at, now()) "
        "FROM candidates WHERE notes IS NOT NULL AND btrim(notes) <> ''"
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_tags_tag", table_name="candidate_tags")
    op.drop_index("ix_candidate_tags_candidate_id", table_name="candidate_tags")
    op.drop_table("candidate_tags")
    op.drop_index("ix_notes_application_id", table_name="notes")
    op.drop_index("ix_notes_candidate_id", table_name="notes")
    op.drop_table("notes")
