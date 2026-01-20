"""set to null

Revision ID: d9003d3b3a73
Revises: 78d6b8b61838
Create Date: 2026-01-16 14:00:12.016769

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9003d3b3a73'
down_revision: Union[str, Sequence[str], None] = '78d6b8b61838'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
