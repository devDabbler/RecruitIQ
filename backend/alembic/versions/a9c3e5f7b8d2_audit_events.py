"""audit_events: who touched candidate data, when, through which endpoint

Pilot plan Track 1 #3. One row per request a staff account makes against a
route that reads or changes candidate data (classification lives in
backend/services/audit_service.py). Rows carry identifiers and field names
only, never values or row copies, so the log itself holds no personal data
beyond pseudonymous ids.

Append-only at the database level: a trigger refuses UPDATE and DELETE
unless the session sets `recruitiq.audit_maintenance = on`, which only a
deliberate maintenance job (a future retention window) should do.

No foreign keys on purpose: an event must outlive the candidate it is about
(the erasure is itself an audited event) and the staff account that made it.

Revision ID: a9c3e5f7b8d2
Revises: f7b1d4e5a6c7
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9c3e5f7b8d2"
down_revision: Union[str, None] = "f7b1d4e5a6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("actor_role", sa.String(20), nullable=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("candidate_id", sa.String(36), nullable=True),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("detail", sa.String(64), nullable=True),
        sa.Column("fields", postgresql.JSONB(), nullable=True),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_candidate", "audit_events", ["candidate_id", "id"])
    op.create_index("ix_audit_events_actor", "audit_events", ["actor_id", "id"])

    op.execute(
        """
        CREATE FUNCTION audit_events_append_only() RETURNS trigger AS $$
        BEGIN
            IF current_setting('recruitiq.audit_maintenance', true) = 'on' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION audit_events_append_only()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_append_only()")
    op.drop_table("audit_events")
