"""Recreate weaviate_data_versions table

Revision ID: c72612262c72
Revises: 3110dc4c039d
Create Date: 2025-12-17 18:36:01.383735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c72612262c72'
down_revision: Union[str, Sequence[str], None] = '3110dc4c039d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create weaviate_data_versions table if it doesn't exist
    op.create_table('weaviate_data_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('weaviate_data_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('change_description', sa.Text(), nullable=True),
        sa.Column('old_values', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('new_values', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('diff', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('operation', sa.String(length=50), nullable=False, server_default='UPDATE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], name='weaviate_data_versions_changed_by_fkey'),
        sa.ForeignKeyConstraint(['weaviate_data_id'], ['weaviate_data.id'], name='weaviate_data_versions_weaviate_data_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='weaviate_data_versions_pkey')
    )
    op.create_index('ix_weaviate_data_versions_weaviate_data_id', 'weaviate_data_versions', ['weaviate_data_id'], unique=False)
    op.create_index('ix_weaviate_data_versions_changed_by', 'weaviate_data_versions', ['changed_by'], unique=False)
    op.create_index('ix_weaviate_data_versions_changed_at', 'weaviate_data_versions', ['changed_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_weaviate_data_versions_changed_at', table_name='weaviate_data_versions')
    op.drop_index('ix_weaviate_data_versions_changed_by', table_name='weaviate_data_versions')
    op.drop_index('ix_weaviate_data_versions_weaviate_data_id', table_name='weaviate_data_versions')
    op.drop_table('weaviate_data_versions')
