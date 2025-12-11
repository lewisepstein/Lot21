"""add_server_default_to_content_created_on

Revision ID: 3ad92f847de8
Revises: 269ae6eb3f44
Create Date: 2025-12-11 19:17:57.867547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ad92f847de8'
down_revision: Union[str, Sequence[str], None] = '269ae6eb3f44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add server_default to created_on column
    op.alter_column('content', 'created_on',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('NOW()'),
                    existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove server_default from created_on column
    op.alter_column('content', 'created_on',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    existing_nullable=False)
