"""
Add skills field to jobs table
Revision ID: 20250416_add_skills_to_jobs
Revises: 
Create Date: 2025-04-16 15:00:06
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250416_add_skills_to_jobs'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('jobs', sa.Column('skills', sa.String(), nullable=True))

def downgrade():
    op.drop_column('jobs', 'skills')
