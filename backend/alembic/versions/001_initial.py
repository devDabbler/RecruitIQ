"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2025-04-15 05:08:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create tables
    op.create_table('candidates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('headline', sa.String(length=255), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('position_applied', sa.String(length=255), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('skills', sa.Text(), nullable=True),
        sa.Column('current_position', sa.String(length=255), nullable=True),
        sa.Column('current_company', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_candidates_email'), 'candidates', ['email'], unique=True)
    
    op.create_table('resumes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(length=255), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('file_type', sa.String(length=50), nullable=True),
        sa.Column('parsed_content', sa.Text(), nullable=True),
        sa.Column('parsed_data', sa.JSON(), nullable=True),
        sa.Column('vector_embedding', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('resumes')
    op.drop_table('candidates')
