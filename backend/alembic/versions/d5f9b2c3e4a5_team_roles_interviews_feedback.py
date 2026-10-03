"""team roles, interviews, feedback, stage default interviewers

ATS Phase B (spec 2026-10-03 sections 3.1, 3.2, 8). Adds users.name and
users.timezone, jobs.hiring_manager_id and jobs.recruiter_id, and the three
tables that turn interview assignments and feedback into rows.

No backfill. Existing users keep their role (admin and demo are both still
valid) and have no name until they set one in Settings. users.role is a
plain varchar, so the four staff roles need no type change.

Revision ID: d5f9b2c3e4a5
Revises: c4e8a1b2d3f4
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5f9b2c3e4a5"
down_revision: Union[str, None] = "c4e8a1b2d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("timezone", sa.String(64), nullable=True))

    op.add_column(
        "jobs",
        sa.Column(
            "hiring_manager_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_jobs_hiring_manager_id"),
            nullable=True,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "recruiter_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_jobs_recruiter_id"),
            nullable=True,
        ),
    )

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_stage_id",
            sa.Integer(),
            sa.ForeignKey("application_stages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("interviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assignment_source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "application_stage_id", "interviewer_id", name="uq_interview_stage_interviewer"
        ),
    )
    op.create_index("ix_interviews_application_stage_id", "interviews", ["application_stage_id"])
    op.create_index("ix_interviews_interviewer_id", "interviews", ["interviewer_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "interview_id",
            sa.Integer(),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("recommendation", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
    )

    op.create_table(
        "stage_default_interviewers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pipeline_stage_id",
            sa.Integer(),
            sa.ForeignKey("pipeline_stages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("pipeline_stage_id", "user_id", name="uq_stage_default_interviewer"),
    )
    op.create_index(
        "ix_stage_default_interviewers_pipeline_stage_id",
        "stage_default_interviewers",
        ["pipeline_stage_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stage_default_interviewers_pipeline_stage_id", table_name="stage_default_interviewers"
    )
    op.drop_table("stage_default_interviewers")
    op.drop_table("feedback")
    op.drop_index("ix_interviews_interviewer_id", table_name="interviews")
    op.drop_index("ix_interviews_application_stage_id", table_name="interviews")
    op.drop_table("interviews")
    op.drop_constraint("fk_jobs_recruiter_id", "jobs", type_="foreignkey")
    op.drop_constraint("fk_jobs_hiring_manager_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "recruiter_id")
    op.drop_column("jobs", "hiring_manager_id")
    op.drop_column("users", "timezone")
    op.drop_column("users", "name")
