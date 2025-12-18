"""add page_id and content_id to weaviate_data

Revision ID: b2c7cab709de
Revises: c72612262c72
Create Date: 2025-12-18 10:48:06.840985

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c7cab709de'
down_revision: Union[str, Sequence[str], None] = 'c72612262c72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add page_id column with foreign key to pages table
    op.add_column('weaviate_data', sa.Column('page_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_weaviate_data_page_id'), 'weaviate_data', ['page_id'], unique=False)
    op.create_foreign_key('fk_weaviate_data_page_id', 'weaviate_data', 'pages', ['page_id'], ['id'], ondelete='SET NULL')
    
    # Add content_id column with foreign key to content table
    op.add_column('weaviate_data', sa.Column('content_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_weaviate_data_content_id'), 'weaviate_data', ['content_id'], unique=False)
    op.create_foreign_key('fk_weaviate_data_content_id', 'weaviate_data', 'content', ['content_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    # Drop content_id column and its constraints
    op.drop_constraint('fk_weaviate_data_content_id', 'weaviate_data', type_='foreignkey')
    op.drop_index(op.f('ix_weaviate_data_content_id'), table_name='weaviate_data')
    op.drop_column('weaviate_data', 'content_id')
    
    # Drop page_id column and its constraints
    op.drop_constraint('fk_weaviate_data_page_id', 'weaviate_data', type_='foreignkey')
    op.drop_index(op.f('ix_weaviate_data_page_id'), table_name='weaviate_data')
    op.drop_column('weaviate_data', 'page_id')
