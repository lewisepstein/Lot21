"""modifications

Revision ID: 78a53c35542a
Revises: 3ad92f847de8
Create Date: 2025-12-11 19:40:42.410646

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78a53c35542a'
down_revision: Union[str, Sequence[str], None] = '3ad92f847de8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
