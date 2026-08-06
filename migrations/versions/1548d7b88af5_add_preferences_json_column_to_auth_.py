"""add preferences json column to auth_users

Revision ID: 1548d7b88af5
Revises: 673bef7bd9d1
Create Date: 2026-08-06 22:51:24.123250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1548d7b88af5'
down_revision: Union[str, Sequence[str], None] = '673bef7bd9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('auth_users', sa.Column('preferences', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('auth_users', 'preferences')
