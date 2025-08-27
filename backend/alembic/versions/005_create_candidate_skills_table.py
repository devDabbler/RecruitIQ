# python
"""Create candidate_skills table"""

revision = '005_cand_skills'
down_revision = '004_add_full_text_column'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.create_table(
        'candidate_skills',
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('candidate_id', 'skill_id')
    )

def downgrade():
    op.drop_table('candidate_skills')
