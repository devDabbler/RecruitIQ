# python
"""Add full_text column to resumes"""

revision = '004_add_full_text_column'
down_revision = '003_add_content_type_column'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('resumes', sa.Column('full_text', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('resumes', 'full_text')
