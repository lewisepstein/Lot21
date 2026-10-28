"""Add standing_instructions column to users table

Revision ID: c4d8e1f2a7b3
Revises: b3f4e7a2c9d1
Create Date: 2026-10-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d8e1f2a7b3'
down_revision: Union[str, Sequence[str], None] = 'b3f4e7a2c9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('standing_instructions', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'standing_instructions')
