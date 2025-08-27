from alembic import op
import sqlalchemy as sa

revision = '003_add_content_type_column'
down_revision = '002_add_file_id_column'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('resumes', sa.Column('content_type', sa.String(), nullable=True))

def downgrade():
    op.drop_column('resumes', 'content_type')
