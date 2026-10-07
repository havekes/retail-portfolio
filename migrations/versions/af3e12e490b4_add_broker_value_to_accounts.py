"""add broker value to accounts

Revision ID: af3e12e490b4
Revises: e25265d203b2
Create Date: 2026-10-07 21:51:25.825474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af3e12e490b4'
down_revision: Union[str, Sequence[str], None] = 'e25265d203b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('accounts', sa.Column('broker_value', sa.Numeric(precision=18, scale=2), nullable=True))
    op.add_column('accounts', sa.Column('broker_value_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('accounts', 'broker_value_at')
    op.drop_column('accounts', 'broker_value')
