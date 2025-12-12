"""move_fk_from_prompt_history_to_task_runs

Revision ID: dc918bb72e5f
Revises: 1fa731e84931
Create Date: 2025-12-12 12:59:22.467688

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc918bb72e5f'
down_revision: Union[str, Sequence[str], None] = '1fa731e84931'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Move foreign key from prompt_history to task_runs."""
    # Add prompt_history_id to task_runs
    op.add_column('task_runs', sa.Column('prompt_history_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_task_runs_prompt_history', 'task_runs', 'prompt_history', ['prompt_history_id'], ['id'])
    
    # Drop foreign key and column from prompt_history
    op.drop_constraint('prompt_history_task_run_id_fkey', 'prompt_history', type_='foreignkey')
    op.drop_column('prompt_history', 'task_run_id')


def downgrade() -> None:
    """Downgrade schema - Move foreign key back to prompt_history."""
    # Add task_run_id back to prompt_history
    op.add_column('prompt_history', sa.Column('task_run_id', sa.Integer(), nullable=True))
    op.create_foreign_key('prompt_history_task_run_id_fkey', 'prompt_history', 'task_runs', ['task_run_id'], ['id'])
    
    # Drop foreign key and column from task_runs
    op.drop_constraint('fk_task_runs_prompt_history', 'task_runs', type_='foreignkey')
    op.drop_column('task_runs', 'prompt_history_id')
