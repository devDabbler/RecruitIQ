"""Add file_id column to resumes table

Revision ID: 002
Revises: 001
Create Date: 2025-04-15 05:12:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_add_file_id_column'
down_revision = '001_initial'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('resumes', sa.Column('file_id', sa.String(255), nullable=True))
    op.create_index(op.f('ix_resumes_file_id'), 'resumes', ['file_id'], unique=True)

def downgrade():
    op.drop_index(op.f('ix_resumes_file_id'), table_name='resumes')
    op.drop_column('resumes', 'file_id')
