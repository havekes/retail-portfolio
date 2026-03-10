"""add mapped_symbol and mapped_exchange to security_broker

Revision ID: a1b2c3d4e5f6
Revises: 0d99570e56cf
Create Date: 2026-03-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "0d99570e56cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "market_securities_broker",
        sa.Column("mapped_symbol", sa.String(), nullable=False),
    )
    op.add_column(
        "market_securities_broker",
        sa.Column("mapped_exchange", sa.String(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("market_securities_broker", "mapped_exchange")
    op.drop_column("market_securities_broker", "mapped_symbol")
