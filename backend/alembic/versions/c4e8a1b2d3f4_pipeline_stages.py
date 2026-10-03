"""pipeline_stages and application_stages, with backfill

ATS Phase A (spec 2026-10-03 section 3). Creates the two tables, moves
job_applications.status to the new vocabulary (active, hired, rejected,
declined, withdrawn), then backfills: every existing job gets the 11 default
stages, and every existing application gets one row per stage positioned
from the candidate's current status, so the board is populated the moment
the code deploys and no reseed is needed on the droplet.

The stage list is duplicated here on purpose rather than imported from
pipeline_service: a migration must describe the schema as of its own
revision, not as of whatever the code says later.

Revision ID: c4e8a1b2d3f4
Revises: b7d2e9a41c53
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a1b2d3f4"
down_revision: Union[str, None] = "b7d2e9a41c53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (key, name, kind, description)
DEFAULT_STAGES = [
    ("resume_submitted", "Resume submitted", "round", "We have your resume and are reviewing it."),
    ("hm_review", "Hiring manager review", "round", "The hiring manager reviews your background against the role."),
    ("technical_written", "Technical assessment", "round", "A take-home or written exercise on the fundamentals of the role."),
    ("technical_interview", "Technical interview", "round", "A live conversation going deep on your primary area."),
    ("problem_solving", "Problem solving", "round", "An open-ended reasoning session with the team."),
    ("case_study", "Case study", "round", "A scenario-based discussion with a small panel."),
    ("hr_screen", "HR screen", "round", "A final conversation about logistics, timing, and references."),
    ("offer", "Offer", "round", "An offer has been extended."),
    ("offer_accepted", "Offer accepted", "round", "You have accepted. We are completing paperwork and a start date."),
    ("offer_declined", "Offer declined", "outcome", "You declined the offer."),
    ("hired", "Hired", "outcome", "Welcome aboard."),
]

# candidate.status -> (index of the in-progress round, application status)
# Indexes are 0-based into DEFAULT_STAGES. None means no round is in progress
# because the application is terminal.
STATUS_SNAPSHOT = {
    "active": (0, "active"),
    "screening": (1, "active"),
    "interviewing": (3, "active"),
    "offered": (7, "active"),
    "on_hold": (1, "active"),
    "hired": (None, "hired"),
    "rejected": (None, "rejected"),
    "withdrawn": (None, "withdrawn"),
}


def upgrade() -> None:
    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="round"),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("job_id", "key", name="uq_pipeline_stage_job_key"),
    )
    op.create_index("ix_pipeline_stages_job_id", "pipeline_stages", ["job_id"])

    op.create_table(
        "application_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("job_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_id",
            sa.Integer(),
            sa.ForeignKey("pipeline_stages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("changed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("application_id", "stage_id", name="uq_application_stage"),
    )
    op.create_index("ix_application_stages_application_id", "application_stages", ["application_id"])
    op.create_index("ix_application_stages_stage_id", "application_stages", ["stage_id"])

    # Old vocabulary: submitted, reviewing, interviewing, accepted, rejected.
    op.execute("UPDATE job_applications SET status = 'hired' WHERE status = 'accepted'")
    op.execute(
        "UPDATE job_applications SET status = 'active' "
        "WHERE status NOT IN ('hired', 'rejected', 'declined', 'withdrawn')"
    )

    bind = op.get_bind()

    # Every existing job gets the default stages.
    for job_id, in bind.execute(sa.text("SELECT id FROM jobs")).fetchall():
        for position, (key, name, kind, description) in enumerate(DEFAULT_STAGES, start=1):
            bind.execute(
                sa.text(
                    "INSERT INTO pipeline_stages (job_id, key, name, description, kind, position, enabled) "
                    "VALUES (:job_id, :key, :name, :description, :kind, :position, true)"
                ),
                {
                    "job_id": job_id,
                    "key": key,
                    "name": name,
                    "description": description,
                    "kind": kind,
                    "position": position,
                },
            )

    # Every existing application gets a row per stage, positioned from the
    # candidate's status (the only funnel signal the old schema had).
    rows = bind.execute(
        sa.text(
            "SELECT a.id, a.job_id, a.status, a.applied_at, c.status AS candidate_status "
            "FROM job_applications a JOIN candidates c ON c.id = a.candidate_id"
        )
    ).fetchall()
    for app_id, job_id, app_status, applied_at, candidate_status in rows:
        stage_ids = bind.execute(
            sa.text(
                "SELECT id, key FROM pipeline_stages WHERE job_id = :job_id ORDER BY position"
            ),
            {"job_id": job_id},
        ).fetchall()
        current_index, derived_status = STATUS_SNAPSHOT.get(candidate_status or "active", (0, "active"))
        if app_status in ("hired", "rejected", "declined", "withdrawn"):
            derived_status = app_status
            current_index = None
        for index, (stage_id, key) in enumerate(stage_ids):
            if derived_status == "hired":
                status = "passed" if key != "offer_declined" else "skipped"
            elif derived_status in ("rejected", "withdrawn", "declined"):
                if index == 0:
                    status = "passed"
                elif index == 1:
                    status = "failed" if derived_status == "rejected" else "skipped"
                else:
                    status = "skipped"
            elif current_index is None or index < current_index:
                status = "passed"
            elif index == current_index:
                status = "in_progress"
            else:
                status = "pending"
            bind.execute(
                sa.text(
                    "INSERT INTO application_stages (application_id, stage_id, status, started_at, completed_at) "
                    "VALUES (:application_id, :stage_id, :status, :started_at, :completed_at)"
                ),
                {
                    "application_id": app_id,
                    "stage_id": stage_id,
                    "status": status,
                    "started_at": applied_at if status != "pending" else None,
                    "completed_at": applied_at if status in ("passed", "failed", "skipped") else None,
                },
            )
        bind.execute(
            sa.text("UPDATE job_applications SET status = :status WHERE id = :id"),
            {"status": derived_status, "id": app_id},
        )


def downgrade() -> None:
    op.drop_index("ix_application_stages_stage_id", table_name="application_stages")
    op.drop_index("ix_application_stages_application_id", table_name="application_stages")
    op.drop_table("application_stages")
    op.drop_index("ix_pipeline_stages_job_id", table_name="pipeline_stages")
    op.drop_table("pipeline_stages")
    op.execute("UPDATE job_applications SET status = 'accepted' WHERE status = 'hired'")
    op.execute(
        "UPDATE job_applications SET status = 'submitted' "
        "WHERE status IN ('active', 'declined', 'withdrawn')"
    )
