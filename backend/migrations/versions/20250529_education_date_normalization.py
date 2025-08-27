"""education date normalization

Revision ID: 20250529_edu_dates
Revises: 20250529_resume_tracking
Create Date: 2025-05-29 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250529_edu_dates'
down_revision = '20250529_resume_tracking'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create education table if it doesn't exist
    op.create_table(
        'education',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.String(36), nullable=False),
        sa.Column('institution', sa.String(255), nullable=False),
        sa.Column('degree', sa.String(255), nullable=True),
        sa.Column('field_of_study', sa.String(255), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('gpa', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_education_candidate_id', 'education', ['candidate_id'])
    op.create_index('ix_education_start_date', 'education', ['start_date'])
    op.create_index('ix_education_end_date', 'education', ['end_date'])
    
    # Add check constraints for date format
    op.execute("""
        ALTER TABLE education
        ADD CONSTRAINT check_start_date_format
        CHECK (start_date IS NULL OR start_date::text ~ '^\d{4}-\d{2}-\d{2}$')
    """)
    
    op.execute("""
        ALTER TABLE education
        ADD CONSTRAINT check_end_date_format
        CHECK (end_date IS NULL OR end_date::text ~ '^\d{4}-\d{2}-\d{2}$')
    """)

def downgrade() -> None:
    # Drop check constraints
    op.execute('ALTER TABLE education DROP CONSTRAINT IF EXISTS check_start_date_format')
    op.execute('ALTER TABLE education DROP CONSTRAINT IF EXISTS check_end_date_format')
    
    # Drop indexes
    op.drop_index('ix_education_end_date', table_name='education')
    op.drop_index('ix_education_start_date', table_name='education')
    op.drop_index('ix_education_candidate_id', table_name='education')
    
    # Drop table
    op.drop_table('education') 