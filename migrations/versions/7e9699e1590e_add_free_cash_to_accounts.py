"""add free cash to accounts

Revision ID: 7e9699e1590e
Revises: 3436586a755f
Create Date: 2026-09-30 17:52:17.452073

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e9699e1590e'
down_revision: Union[str, Sequence[str], None] = '3436586a755f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('accounts', sa.Column('free_cash', sa.Float(), server_default='0.0', nullable=False))
    op.execute(
        "UPDATE market_securities SET currency = 'CAD' WHERE symbol = 'CASH' AND exchange = 'TO' AND currency = 'USD'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('accounts', 'free_cash')
