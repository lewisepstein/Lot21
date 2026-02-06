"""add freeform tables

Revision ID: b3f4e7a2c9d1
Revises: a610df39808c
Create Date: 2026-02-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3f4e7a2c9d1'
down_revision: Union[str, Sequence[str], None] = 'a610df39808c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create ChatRoleEnum if it doesn't exist
    connection = op.get_bind()
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE chatroleenum AS ENUM ('USER', 'ASSISTANT', 'SYSTEM');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # Create ChatTypeEnum if it doesn't exist
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE chattypeenum AS ENUM ('TEXT', 'IMAGE', 'MULTIMODAL');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # Create freeform_projects table
    op.create_table(
        'freeform_projects',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_name', sa.String(length=255), nullable=False),
        sa.Column('project_description', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_on', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_on', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_freeform_projects_project_name'), 'freeform_projects', ['project_name'], unique=False)

    # Create freeform_chat table
    op.create_table(
        'freeform_chat',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('role', postgresql.ENUM('USER', 'ASSISTANT', 'SYSTEM', name='chatroleenum', create_type=False), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('content_type', postgresql.ENUM('TEXT', 'IMAGE', 'MULTIMODAL', name='chattypeenum', create_type=False), nullable=False),
        sa.Column('attachments', sa.Text(), nullable=True),
        sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_on', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['freeform_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_freeform_chat_project_id'), 'freeform_chat', ['project_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables
    op.drop_index(op.f('ix_freeform_chat_project_id'), table_name='freeform_chat')
    op.drop_table('freeform_chat')
    op.drop_index(op.f('ix_freeform_projects_project_name'), table_name='freeform_projects')
    op.drop_table('freeform_projects')

    # Drop enums
    chat_type_enum = postgresql.ENUM('TEXT', 'IMAGE', 'MULTIMODAL', name='chattypeenum')
    chat_type_enum.drop(op.get_bind(), checkfirst=True)

    chat_role_enum = postgresql.ENUM('USER', 'ASSISTANT', 'SYSTEM', name='chatroleenum')
    chat_role_enum.drop(op.get_bind(), checkfirst=True)
