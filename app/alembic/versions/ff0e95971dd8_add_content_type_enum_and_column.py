"""add_content_type_enum_and_column

Revision ID: ff0e95971dd8
Revises: ff36f8e53e76
Create Date: 2025-12-16 10:36:22.178302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ff0e95971dd8'
down_revision: Union[str, Sequence[str], None] = 'ff36f8e53e76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum type first
    content_type_enum = postgresql.ENUM('UNDERSTANDING', 'PROJECTS', 'RESOURCES', 'POLICY', 'LOTS', 'NEWSLETTER', 'SOCIAL', name='contenttypeenum')
    content_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Add content_type column to content table
    op.add_column('content', sa.Column('content_type', sa.Enum('UNDERSTANDING', 'PROJECTS', 'RESOURCES', 'POLICY', 'LOTS', 'NEWSLETTER', 'SOCIAL', name='contenttypeenum'), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop content_type column
    op.drop_column('content', 'content_type')
    
    # Drop the enum type
    content_type_enum = postgresql.ENUM('UNDERSTANDING', 'PROJECTS', 'RESOURCES', 'POLICY', 'LOTS', 'NEWSLETTER', 'SOCIAL', name='contenttypeenum')
    content_type_enum.drop(op.get_bind(), checkfirst=True)
