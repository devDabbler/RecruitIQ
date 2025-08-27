"""Fix candidate_skills table structure

Revision ID: 20250529_fix_skills
Revises: 20250529_resume_tracking
Create Date: 2025-05-29 17:59:57.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250529_fix_skills'
down_revision = '20250529_resume_tracking'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Drop existing candidate_skills table and its constraints
    op.drop_table('candidate_skills')
    
    # Recreate candidate_skills table with the new structure
    op.create_table('candidate_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.String(36), nullable=False),
        sa.Column('skill_name', sa.String(255), nullable=False),
        sa.Column('proficiency', sa.String(50), nullable=True),
        sa.Column('years_of_experience', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('candidate_id', 'skill_name', name='unique_candidate_skill')
    )

def downgrade() -> None:
    # Drop the new candidate_skills table
    op.drop_table('candidate_skills')
    
    # Recreate the original association table
    op.create_table('candidate_skills',
        sa.Column('candidate_id', sa.String(36), nullable=False),
        sa.Column('skill_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('candidate_id', 'skill_id'),
        sa.UniqueConstraint('candidate_id', 'skill_id', name='uq_candidate_skill')
    )
