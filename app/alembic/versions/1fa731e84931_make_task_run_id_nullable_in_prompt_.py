"""make_task_run_id_nullable_in_prompt_history

Revision ID: 1fa731e84931
Revises: 98226d85ddb9
Create Date: 2025-12-12 12:56:30.357794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1fa731e84931'
down_revision: Union[str, Sequence[str], None] = '98226d85ddb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Make task_run_id nullable in prompt_history."""
    op.alter_column('prompt_history', 'task_run_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema - Make task_run_id not nullable."""
    op.alter_column('prompt_history', 'task_run_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)
