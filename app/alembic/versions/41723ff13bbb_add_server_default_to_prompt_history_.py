"""add_server_default_to_prompt_history_created_on

Revision ID: 41723ff13bbb
Revises: dc918bb72e5f
Create Date: 2025-12-12 14:34:47.927415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41723ff13bbb'
down_revision: Union[str, Sequence[str], None] = 'dc918bb72e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add server_default to prompt_history.created_on."""
    op.alter_column('prompt_history', 'created_on',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('NOW()'),
                    nullable=False)


def downgrade() -> None:
    """Downgrade schema - Remove server_default from prompt_history.created_on."""
    op.alter_column('prompt_history', 'created_on',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    nullable=False)
