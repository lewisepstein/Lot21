"""empty message

Revision ID: a610df39808c
Revises: 9b2b2aa5a7c9
Create Date: 2026-02-03 11:07:41.346284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a610df39808c'
down_revision: Union[str, Sequence[str], None] = '9b2b2aa5a7c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('prompt_history', 'content_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('prompt_history', 'content_id', existing_type=sa.Integer(), nullable=False)
