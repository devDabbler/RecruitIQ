"""pgvector 768 embeddings

Revision ID: e847c752f9f2
Revises: 716ed00c4df0
Create Date: 2026-08-27 05:30:59.456181

Neo4j is removed in Phase 1b; pgvector becomes the vector store. Embeddings
are 768-dim (nomic-embed-text via ollama) instead of the old 384-dim
all-MiniLM-L6-v2 that lived in Neo4j.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'e847c752f9f2'
down_revision: Union[str, None] = '716ed00c4df0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # agent_memories was 384-dim in the baseline and only created where pgvector
    # existed - i.e. nowhere real (the live DB had no pgvector until Phase 1b).
    # Recreate at 768 unconditionally; the table is empty everywhere.
    op.execute("DROP TABLE IF EXISTS agent_memories")
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agent_session_time", "agent_memories", ["agent_name", "session_id", "created_at"], unique=False)
    op.create_index(op.f("ix_agent_memories_agent_name"), "agent_memories", ["agent_name"], unique=False)
    op.create_index(op.f("ix_agent_memories_id"), "agent_memories", ["id"], unique=False)
    op.create_index(op.f("ix_agent_memories_session_id"), "agent_memories", ["session_id"], unique=False)

    op.add_column("jobs", sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True))
    op.add_column("candidates", sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True))

    op.execute("CREATE INDEX ix_jobs_embedding_hnsw ON jobs USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX ix_candidates_embedding_hnsw ON candidates USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_candidates_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_jobs_embedding_hnsw")
    op.drop_column("candidates", "embedding")
    op.drop_column("jobs", "embedding")
    op.execute("DROP TABLE IF EXISTS agent_memories")
