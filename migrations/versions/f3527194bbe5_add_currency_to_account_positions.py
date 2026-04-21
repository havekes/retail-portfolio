"""Add currency to account_positions

Revision ID: f3527194bbe5
Revises: cdec46de51af
Create Date: 2026-04-21 00:57:26.809986

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3527194bbe5'
down_revision: Union[str, Sequence[str], None] = 'cdec46de51af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('account_positions', sa.Column('currency', sa.String(length=3), nullable=True))
    op.execute(
        "UPDATE account_positions SET currency = market_securities.currency "
        "FROM market_securities "
        "WHERE account_positions.security_id = market_securities.id"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('account_positions', 'currency')
