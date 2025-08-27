"""add resume tracking fields

Revision ID: 20250529_add_resume_tracking_fields
Revises: 20250417_102326_add_embeddings_to_jobs
Create Date: 2025-05-29 07:42:42.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250529_add_resume_tracking_fields'
down_revision = '20250417_102326_add_embeddings_to_jobs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to resumes table
    op.add_column('resumes', sa.Column('parser_version', sa.String(50), nullable=True))
    op.add_column('resumes', sa.Column('validation_status', sa.String(50), server_default='pending'))
    op.add_column('resumes', sa.Column('validation_score', sa.Float(), nullable=True))
    op.add_column('resumes', sa.Column('last_synced_to_neo4j', sa.DateTime(), nullable=True))
    
    # Create GIN indexes on parsed_data JSONB column
    op.execute('CREATE INDEX IF NOT EXISTS idx_parsed_data_email ON resumes USING gin (parsed_data)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_parsed_data_skills ON resumes USING gin (parsed_data)')


def downgrade() -> None:
    # Drop indexes first
    op.execute('DROP INDEX IF EXISTS idx_parsed_data_email')
    op.execute('DROP INDEX IF EXISTS idx_parsed_data_skills')
    
    # Drop columns from resumes table
    op.drop_column('resumes', 'last_synced_to_neo4j')
    op.drop_column('resumes', 'validation_score')
    op.drop_column('resumes', 'validation_status')
    op.drop_column('resumes', 'parser_version')
