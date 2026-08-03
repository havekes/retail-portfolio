"""add_intraday_prices_table

Revision ID: 4d2535bc952f
Revises: cb09d71c3f7d
Create Date: 2026-08-03 17:29:13.325894

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d2535bc952f'
down_revision: Union[str, Sequence[str], None] = 'cb09d71c3f7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the market_intraday_prices table backing IntradayPriceModel.

    This table supports 1-hour resolution candle retrieval
    (IntradayPriceRepository.get_intraday_prices).
    """
    op.create_table(
        'market_intraday_prices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('security_id', sa.Uuid(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.DECIMAL(precision=16, scale=8), nullable=False),
        sa.Column('high', sa.DECIMAL(precision=16, scale=8), nullable=False),
        sa.Column('low', sa.DECIMAL(precision=16, scale=8), nullable=False),
        sa.Column('close', sa.DECIMAL(precision=16, scale=8), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ['security_id'], ['market_securities.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'security_id', 'timestamp',
            name='intraday_price_security_timestamp_unique',
        ),
    )


def downgrade() -> None:
    """Drop the market_intraday_prices table."""
    op.drop_table('market_intraday_prices')
