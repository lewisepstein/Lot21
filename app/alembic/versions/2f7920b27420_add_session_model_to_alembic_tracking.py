"""add session model to alembic tracking

Revision ID: 2f7920b27420
Revises: abc123def456
Create Date: 2025-12-18 14:43:46.115936

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2f7920b27420'
down_revision: Union[str, Sequence[str], None] = 'abc123def456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Sessions table already created in previous migration (abc123def456)
    # This migration just adds the Session model to Alembic tracking
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # No changes to downgrade
    pass
