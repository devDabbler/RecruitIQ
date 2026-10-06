"""Job and intake hygiene: requisition numbers, departments, sources, withdrawn

Track 2 Phase 3, four small changes in one revision:

1. jobs.requisition_number, nullable String(40), unique when set (a partial
   unique index, so any number of jobs may leave it empty).
2. A departments table (names unique ignoring case) seeded from the
   distinct department names jobs already carry, after trimming them and
   collapsing case variants to the most used spelling, so every existing
   job stays valid under the new check.
3. job_applications.source moved to one vocabulary (the CandidateSource
   values plus `internal`): `direct` and `resume_upload` become
   `direct_application`, anything else unknown (including blank) becomes
   `other`. candidates.source gets the same mapping where it is set.
4. A `withdrawn` outcome stage on every job that has stages, and a row for
   it on every application that has stage rows: passed for applications
   already withdrawn (at the moment their last stage closed), pending for
   active ones, skipped for the rest.

The vocabulary and stage are written out here rather than imported: a
migration describes the schema as of its own revision.

Revision ID: c8e2f4a6b9d1
Revises: b1d4f6a8c2e3
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8e2f4a6b9d1"
down_revision: Union[str, None] = "b1d4f6a8c2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOURCES = (
    "linkedin",
    "indeed",
    "company_website",
    "referral",
    "agency",
    "job_board",
    "direct_application",
    "other",
    "internal",
)
WITHDRAWN = ("withdrawn", "Withdrawn", "outcome", "You withdrew from the process.")

_SOURCE_CASE = """
    CASE
        WHEN lower(trim(source)) IN :known THEN lower(trim(source))
        WHEN lower(trim(source)) IN ('direct', 'resume_upload') THEN 'direct_application'
        ELSE 'other'
    END
"""


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Requisition numbers.
    op.add_column("jobs", sa.Column("requisition_number", sa.String(40), nullable=True))
    op.create_index(
        "uq_jobs_requisition_number",
        "jobs",
        ["requisition_number"],
        unique=True,
        postgresql_where=sa.text("requisition_number IS NOT NULL"),
    )

    # 2. Departments, seeded from what jobs already say.
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    # Unique ignoring case, so "Engineering" and "engineering" cannot both exist.
    op.create_index("uq_departments_name_lower", "departments", [sa.text("lower(name)")], unique=True)
    # Collapse spellings first: trim, then give every case variant the
    # spelling most jobs use, so "Eng " and "eng" stop being two departments.
    bind.execute(sa.text("UPDATE jobs SET department = trim(department) WHERE department <> trim(department)"))
    bind.execute(
        sa.text(
            """
            UPDATE jobs j SET department = c.name
            FROM (
                SELECT DISTINCT ON (lower(department)) lower(department) AS k, department AS name
                FROM jobs WHERE department IS NOT NULL AND department <> ''
                GROUP BY department
                ORDER BY lower(department), count(*) DESC, department
            ) c
            WHERE lower(j.department) = c.k AND j.department <> c.name
            """
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO departments (name) "
            "SELECT DISTINCT department FROM jobs "
            "WHERE department IS NOT NULL AND department <> ''"
        )
    )

    # 3. One source vocabulary.
    known = sa.bindparam("known", value=SOURCES, expanding=True)
    bind.execute(
        sa.text(f"UPDATE job_applications SET source = {_SOURCE_CASE}").bindparams(known)
    )
    bind.execute(
        sa.text(
            f"UPDATE candidates SET source = {_SOURCE_CASE} "
            "WHERE source IS NOT NULL AND trim(source) <> ''"
        ).bindparams(known)
    )

    # 4. A withdrawn outcome on every job that has stages.
    key, name, kind, description = WITHDRAWN
    bind.execute(
        sa.text(
            "INSERT INTO pipeline_stages (job_id, key, name, kind, description, position, enabled) "
            "SELECT job_id, :key, :name, :kind, :description, max(position) + 1, true "
            "FROM pipeline_stages GROUP BY job_id "
            "HAVING bool_and(key <> :key)"
        ),
        {"key": key, "name": name, "kind": kind, "description": description},
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO application_stages (application_id, stage_id, status, started_at, completed_at)
            SELECT a.id, s.id,
                   CASE
                       WHEN a.status = 'withdrawn' THEN 'passed'
                       WHEN a.status = 'active' THEN 'pending'
                       ELSE 'skipped'
                   END,
                   CASE WHEN a.status = 'withdrawn' THEN closed.at END,
                   CASE WHEN a.status = 'active' THEN NULL ELSE closed.at END
            FROM job_applications a
            JOIN pipeline_stages s ON s.job_id = a.job_id AND s.key = :key
            JOIN LATERAL (
                SELECT coalesce(max(r.completed_at), a.applied_at, now()) AS at
                FROM application_stages r WHERE r.application_id = a.id
            ) closed ON true
            WHERE EXISTS (SELECT 1 FROM application_stages r WHERE r.application_id = a.id)
              AND NOT EXISTS (
                  SELECT 1 FROM application_stages r WHERE r.application_id = a.id AND r.stage_id = s.id
              )
            """
        ),
        {"key": key},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM application_stages WHERE stage_id IN "
            "(SELECT id FROM pipeline_stages WHERE key = 'withdrawn')"
        )
    )
    bind.execute(sa.text("DELETE FROM pipeline_stages WHERE key = 'withdrawn'"))
    # Sources are not mapped back: the old free text carried no information
    # the new vocabulary lost beyond spelling.
    op.drop_table("departments")
    op.drop_index("uq_jobs_requisition_number", table_name="jobs")
    op.drop_column("jobs", "requisition_number")
