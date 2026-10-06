"""jobs.requirements: structured must-have / nice-to-have requirements

Track 2 Phase 1. Nullable JSONB holding must_have_skills,
nice_to_have_skills, min_years, max_years and min_education (validated by
services/job_requirements.JobRequirements). NULL means the job sets no
requirements, and such a job scores exactly as it did before this column
existed.

Revision ID: b1d4f6a8c2e3
Revises: a9c3e5f7b8d2
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1d4f6a8c2e3"
down_revision: Union[str, None] = "a9c3e5f7b8d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("requirements", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "requirements")
