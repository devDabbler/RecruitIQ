"""add views and applications columns to jobs

Revision ID: simple_views_apps
Revises: 2b1dbf93b492
Create Date: 2025-06-30 19:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'simple_views_apps'
down_revision: Union[str, None] = '2b1dbf93b492'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add views and applications columns to jobs table."""
    # Add views column to jobs table
    op.add_column('jobs', sa.Column('views', sa.Integer(), nullable=True, default=0))
    
    # Add applications column to jobs table  
    op.add_column('jobs', sa.Column('applications', sa.Integer(), nullable=True, default=0))


def downgrade() -> None:
    """Remove views and applications columns from jobs table."""
    # Remove the added columns
    op.drop_column('jobs', 'applications')
    op.drop_column('jobs', 'views') 