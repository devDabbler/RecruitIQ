"""Add embedding columns to jobs table

Revision ID: 20250417_add_embeddings
Revises: 20250416_add_skills_to_jobs
Create Date: 2025-04-17 10:23:26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250417_add_embeddings'
down_revision = '20250416_add_skills_to_jobs'
branch_labels = None
depends_on = None

def upgrade():
    # Add JSONB columns for embeddings
    op.add_column('jobs', sa.Column('description_embedding', postgresql.JSONB(), nullable=True))
    op.add_column('jobs', sa.Column('requirements_embedding', postgresql.JSONB(), nullable=True))
    op.add_column('jobs', sa.Column('skills_embedding', postgresql.JSONB(), nullable=True))
    
    # Add an index to improve query performance
    op.create_index(op.f('ix_jobs_description_embedding'), 'jobs', ['description_embedding'], unique=False, 
                    postgresql_using='gin', postgresql_ops={'description_embedding': 'jsonb_path_ops'})

def downgrade():
    # Remove index
    op.drop_index(op.f('ix_jobs_description_embedding'), table_name='jobs')
    
    # Remove columns
    op.drop_column('jobs', 'skills_embedding')
    op.drop_column('jobs', 'requirements_embedding')
    op.drop_column('jobs', 'description_embedding')
