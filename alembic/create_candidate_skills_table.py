"""
Alembic migration script to create the candidate_skills table.
"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

# revision identifiers, used by Alembic.
revision = 'create_candidate_skills_table'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'candidate_skills',
        sa.Column('candidate_id', pg.UUID(as_uuid=True), sa.ForeignKey('candidates.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('skill_id', pg.UUID(as_uuid=True), sa.ForeignKey('skills.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('candidate_id', 'skill_id', name='uq_candidate_skill')
    )

def downgrade():
    op.drop_table('candidate_skills')
