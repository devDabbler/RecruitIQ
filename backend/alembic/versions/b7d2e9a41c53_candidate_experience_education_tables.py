"""candidate_experience and candidate_education tables; candidate_skills timestamp defaults

These two tables were only ever created by a legacy `_ensure_tables_exist`
path in resume_service.py that raw-SQL'd them into whatever database the app
happened to touch first. The current save_resume flow still inserts into
them, but nothing creates them anymore, so a fresh database (CI, the
droplet) 500s on the first resume save. Hand-written with IF NOT EXISTS
because long-lived dev databases already have the tables from the legacy
path. candidate_id is VARCHAR(36), not the UUID the legacy DDL used:
candidates.id is a String(36) in the baseline, so a UUID column cannot
carry the foreign key against this schema.

Also gives candidate_skills.created_at/updated_at server-side now()
defaults. The baseline declared them NOT NULL with no default, relying on
the ORM's Python-side default; save_resume writes skills with raw SQL and
gets a NotNullViolation on any database built purely from migrations.

Revision ID: b7d2e9a41c53
Revises: a3f1c2d40b17
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7d2e9a41c53"
down_revision: Union[str, None] = "a3f1c2d40b17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_education (
            id SERIAL PRIMARY KEY,
            candidate_id VARCHAR(36) NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            institution VARCHAR(255),
            degree VARCHAR(255),
            field_of_study VARCHAR(255),
            start_date DATE,
            end_date DATE,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_experience (
            id SERIAL PRIMARY KEY,
            candidate_id VARCHAR(36) NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            company VARCHAR(255),
            position VARCHAR(255),
            location VARCHAR(255),
            start_date DATE,
            end_date DATE,
            current BOOLEAN,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """
    )


    op.execute("ALTER TABLE candidate_skills ALTER COLUMN created_at SET DEFAULT now()")
    op.execute("ALTER TABLE candidate_skills ALTER COLUMN updated_at SET DEFAULT now()")


def downgrade() -> None:
    op.execute("ALTER TABLE candidate_skills ALTER COLUMN created_at DROP DEFAULT")
    op.execute("ALTER TABLE candidate_skills ALTER COLUMN updated_at DROP DEFAULT")
    op.execute("DROP TABLE IF EXISTS candidate_experience")
    op.execute("DROP TABLE IF EXISTS candidate_education")
