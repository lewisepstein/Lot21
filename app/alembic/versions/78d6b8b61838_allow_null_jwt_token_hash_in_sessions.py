"""allow_null_jwt_token_hash_in_sessions

Revision ID: 78d6b8b61838
Revises: 2f7920b27420
Create Date: 2025-12-18 15:18:41.505689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78d6b8b61838'
down_revision: Union[str, Sequence[str], None] = '2f7920b27420'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow NULL values in jwt_token_hash column."""
    op.alter_column('sessions', 'jwt_token_hash',
                    existing_type=sa.String(length=255),
                    nullable=True)


def downgrade() -> None:
    """Revert jwt_token_hash to NOT NULL."""
    op.alter_column('sessions', 'jwt_token_hash',
                    existing_type=sa.String(length=255),
                    nullable=False)
