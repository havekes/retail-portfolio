"""Add watchlist models

Revision ID: 75fd69f81a15
Revises: 4bc783100e62
Create Date: 2026-03-01 15:49:30.785601

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "75fd69f81a15"
down_revision: str | Sequence[str] | None = "4bc783100e62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "market_watchlists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "market_watchlists_securities",
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["security_id"], ["market_securities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id"], ["market_watchlists.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("watchlist_id", "security_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("market_watchlists_securities")
    op.drop_table("market_watchlists")
