"""baseline: full schema consolidated from three legacy trees

Revision ID: 716ed00c4df0
Revises: 
Create Date: 2026-08-27 04:16:14.279216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '716ed00c4df0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pgvector_available() -> bool:
    bind = op.get_bind()
    return bool(bind.execute(sa.text(
        "SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'"
    )).scalar())


def upgrade() -> None:
    """Upgrade schema."""
    # agent_memories needs the pgvector extension, which the local Postgres
    # does not ship yet (it arrives with the Phase 1b Neo4j -> pgvector
    # move). Create the table only where the extension is installable so
    # the baseline applies cleanly on both kinds of machine.
    if _pgvector_available():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.create_table('agent_memories',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('memory_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('importance', sa.Float(), nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index('idx_agent_session_time', 'agent_memories', ['agent_name', 'session_id', 'created_at'], unique=False)
        op.create_index(op.f('ix_agent_memories_agent_name'), 'agent_memories', ['agent_name'], unique=False)
        op.create_index(op.f('ix_agent_memories_id'), 'agent_memories', ['id'], unique=False)
        op.create_index(op.f('ix_agent_memories_session_id'), 'agent_memories', ['session_id'], unique=False)
    op.create_table('jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('department', sa.String(length=100), nullable=True),
    sa.Column('job_overview', sa.Text(), nullable=True),
    sa.Column('required_qualifications', sa.Text(), nullable=True),
    sa.Column('location', sa.String(length=255), nullable=True),
    sa.Column('location_type', sa.String(length=50), nullable=True),
    sa.Column('job_type', sa.String(length=50), nullable=True),
    sa.Column('experience_level', sa.String(length=50), nullable=True),
    sa.Column('min_salary', sa.Integer(), nullable=True),
    sa.Column('max_salary', sa.Integer(), nullable=True),
    sa.Column('hiring_manager', sa.String(length=255), nullable=True),
    sa.Column('recruiter', sa.String(length=255), nullable=True),
    sa.Column('application_deadline', sa.DateTime(), nullable=True),
    sa.Column('start_date', sa.DateTime(), nullable=True),
    sa.Column('job_metadata', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('skills', sa.String(), nullable=True),
    sa.Column('views', sa.Integer(), nullable=True),
    sa.Column('applications', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_id'), 'jobs', ['id'], unique=False)
    op.create_table('skills',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_skills_id'), 'skills', ['id'], unique=False)
    op.create_table('candidates',
    sa.Column('id', sa.String(length=36), nullable=False),
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
    sa.Column('current_position', sa.String(length=255), nullable=True),
    sa.Column('current_company', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_candidate_created_status', 'candidates', ['created_at', 'status'], unique=False)
    op.create_index('idx_candidate_name_search', 'candidates', ['first_name', 'last_name'], unique=False)
    op.create_index('idx_candidate_status_position', 'candidates', ['status', 'position_applied'], unique=False)
    op.create_index(op.f('ix_candidates_created_at'), 'candidates', ['created_at'], unique=False)
    op.create_index(op.f('ix_candidates_email'), 'candidates', ['email'], unique=True)
    op.create_index(op.f('ix_candidates_first_name'), 'candidates', ['first_name'], unique=False)
    op.create_index(op.f('ix_candidates_id'), 'candidates', ['id'], unique=False)
    op.create_index(op.f('ix_candidates_last_name'), 'candidates', ['last_name'], unique=False)
    op.create_index(op.f('ix_candidates_position_applied'), 'candidates', ['position_applied'], unique=False)
    op.create_index(op.f('ix_candidates_status'), 'candidates', ['status'], unique=False)
    op.create_table('candidate_pitches',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('candidate_id', sa.String(length=36), nullable=True),
    sa.Column('job_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('tags', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_candidate_pitches_id'), 'candidate_pitches', ['id'], unique=False)
    op.create_index(op.f('ix_candidate_pitches_user_id'), 'candidate_pitches', ['user_id'], unique=False)
    op.create_table('candidate_skills',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('candidate_id', sa.String(length=36), nullable=False),
    sa.Column('skill_name', sa.String(length=255), nullable=False),
    sa.Column('proficiency', sa.String(length=50), nullable=True),
    sa.Column('years_of_experience', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('candidate_id', 'skill_name', name='unique_candidate_skill')
    )
    op.create_index(op.f('ix_candidate_skills_id'), 'candidate_skills', ['id'], unique=False)
    op.create_table('job_applications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('candidate_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('cover_letter', sa.Text(), nullable=True),
    sa.Column('applied_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('source', sa.String(length=100), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_job_applications_id'), 'job_applications', ['id'], unique=False)
    op.create_table('resumes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('candidate_id', sa.String(length=36), nullable=True),
    sa.Column('file_id', sa.String(length=255), nullable=True),
    sa.Column('file_path', sa.String(length=255), nullable=True),
    sa.Column('file_name', sa.String(length=255), nullable=True),
    sa.Column('file_type', sa.String(length=50), nullable=True),
    sa.Column('parsed_content', sa.Text(), nullable=True),
    sa.Column('parsed_data', sa.JSON(), nullable=True),
    sa.Column('vector_embedding', sa.JSON(), nullable=True),
    sa.Column('parser_version', sa.String(length=50), nullable=True),
    sa.Column('validation_status', sa.String(length=50), nullable=True),
    sa.Column('validation_score', sa.Float(), nullable=True),
    sa.Column('last_synced_to_neo4j', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # GIN needs jsonb; the live DB indexes the json column through a cast,
    # so the baseline mirrors those expression indexes verbatim.
    op.execute("CREATE INDEX idx_parsed_data_email ON resumes USING gin (((parsed_data)::jsonb))")
    op.execute("CREATE INDEX idx_parsed_data_skills ON resumes USING gin (((parsed_data)::jsonb))")
    op.create_index(op.f('ix_resumes_file_id'), 'resumes', ['file_id'], unique=True)
    op.create_index(op.f('ix_resumes_id'), 'resumes', ['id'], unique=False)
    op.create_table('saved_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('candidate_id', sa.String(length=36), nullable=False),
    sa.Column('saved_at', sa.DateTime(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_id', 'candidate_id', name='unique_job_candidate_save')
    )
    op.create_index(op.f('ix_saved_jobs_id'), 'saved_jobs', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_saved_jobs_id'), table_name='saved_jobs')
    op.drop_table('saved_jobs')
    op.drop_index(op.f('ix_resumes_id'), table_name='resumes')
    op.drop_index(op.f('ix_resumes_file_id'), table_name='resumes')
    op.drop_index('idx_parsed_data_skills', table_name='resumes')
    op.drop_index('idx_parsed_data_email', table_name='resumes')
    op.drop_table('resumes')
    op.drop_index(op.f('ix_job_applications_id'), table_name='job_applications')
    op.drop_table('job_applications')
    op.drop_index(op.f('ix_candidate_skills_id'), table_name='candidate_skills')
    op.drop_table('candidate_skills')
    op.drop_index(op.f('ix_candidate_pitches_user_id'), table_name='candidate_pitches')
    op.drop_index(op.f('ix_candidate_pitches_id'), table_name='candidate_pitches')
    op.drop_table('candidate_pitches')
    op.drop_index(op.f('ix_candidates_status'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_position_applied'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_last_name'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_id'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_first_name'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_email'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_created_at'), table_name='candidates')
    op.drop_index('idx_candidate_status_position', table_name='candidates')
    op.drop_index('idx_candidate_name_search', table_name='candidates')
    op.drop_index('idx_candidate_created_status', table_name='candidates')
    op.drop_table('candidates')
    op.drop_index(op.f('ix_skills_id'), table_name='skills')
    op.drop_table('skills')
    op.drop_index(op.f('ix_jobs_id'), table_name='jobs')
    op.drop_table('jobs')
    if sa.inspect(op.get_bind()).has_table('agent_memories'):
        op.drop_index(op.f('ix_agent_memories_session_id'), table_name='agent_memories')
        op.drop_index(op.f('ix_agent_memories_id'), table_name='agent_memories')
        op.drop_index(op.f('ix_agent_memories_agent_name'), table_name='agent_memories')
        op.drop_index('idx_agent_session_time', table_name='agent_memories')
        op.drop_table('agent_memories')
    # ### end Alembic commands ###
