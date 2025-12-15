"""create_weaviate_data_versions_table

Revision ID: ff36f8e53e76
Revises: 390d4606e1f5
Create Date: 2025-12-15 18:10:03.670409

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff36f8e53e76'
down_revision: Union[str, Sequence[str], None] = '390d4606e1f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'weaviate_data_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('weaviate_data_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('change_description', sa.Text(), nullable=True),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('diff', sa.JSON(), nullable=True),
        sa.Column('operation', sa.String(50), nullable=False, server_default='UPDATE'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['weaviate_data_id'], ['weaviate_data.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='RESTRICT')
    )
    
    # Create indexes for faster queries
    op.create_index('ix_weaviate_data_versions_weaviate_data_id', 'weaviate_data_versions', ['weaviate_data_id'])
    op.create_index('ix_weaviate_data_versions_changed_by', 'weaviate_data_versions', ['changed_by'])
    op.create_index('ix_weaviate_data_versions_changed_at', 'weaviate_data_versions', ['changed_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_weaviate_data_versions_changed_at', table_name='weaviate_data_versions')
    op.drop_index('ix_weaviate_data_versions_changed_by', table_name='weaviate_data_versions')
    op.drop_index('ix_weaviate_data_versions_weaviate_data_id', table_name='weaviate_data_versions')
    op.drop_table('weaviate_data_versions')
