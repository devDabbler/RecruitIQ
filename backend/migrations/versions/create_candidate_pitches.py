"""create candidate_pitches table

Revision ID: create_candidate_pitches
Revises: 4644341b7cec
Create Date: 2025-01-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_candidate_pitches'
down_revision = '4644341b7cec'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create candidate_pitches table
    op.create_table('candidate_pitches',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('candidate_id', sa.String(36), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_candidate_pitches_user_id', 'candidate_pitches', ['user_id'], unique=False)
    op.create_index(op.f('ix_candidate_pitches_id'), 'candidate_pitches', ['id'], unique=False)

def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_candidate_pitches_id'), table_name='candidate_pitches')
    op.drop_index('idx_candidate_pitches_user_id', table_name='candidate_pitches')
    
    # Drop table
    op.drop_table('candidate_pitches') 