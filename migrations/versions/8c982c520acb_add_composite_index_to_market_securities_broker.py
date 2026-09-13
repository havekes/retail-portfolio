"""add_composite_index_to_market_securities_broker

Revision ID: 8c982c520acb
Revises: 5223c29cb058
Create Date: 2026-09-13 20:15:23.953679

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c982c520acb"
down_revision: Union[str, Sequence[str], None] = "5223c29cb058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_market_securities_broker_institution_symbol_exchange",
        "market_securities_broker",
        ["institution_id", "broker_symbol", "broker_exchange"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_market_securities_broker_institution_symbol_exchange",
        table_name="market_securities_broker",
    )
