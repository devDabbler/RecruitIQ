"""merge education and skills heads

Revision ID: 4644341b7cec
Revises: 20250529_fix_skills, 20250529_edu_dates
Create Date: 2025-06-13 21:33:00.892639

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4644341b7cec'
down_revision: Union[str, None] = ('20250529_fix_skills', '20250529_edu_dates')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    pass

def downgrade() -> None:
    """Downgrade schema."""
    pass
