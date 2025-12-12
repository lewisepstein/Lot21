"""add_new_to_contentactionenum

Revision ID: 98226d85ddb9
Revises: 78a53c35542a
Create Date: 2025-12-12 12:55:19.486442

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98226d85ddb9'
down_revision: Union[str, Sequence[str], None] = '78a53c35542a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add 'NEW' value to contentactionenum."""
    # Add NEW value to the enum
    op.execute("ALTER TYPE contentactionenum ADD VALUE 'NEW'")


def downgrade() -> None:
    """Downgrade schema - Cannot remove enum values in PostgreSQL."""
    # Note: PostgreSQL does not support removing enum values
    # A full downgrade would require recreating the enum type
    pass
