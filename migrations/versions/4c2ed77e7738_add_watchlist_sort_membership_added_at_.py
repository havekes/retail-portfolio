"""add watchlist sort, membership added_at and position

Adds:
- ``market_watchlists.sort`` — persisted sort mode, defaults to ``custom``.
- ``market_watchlists_securities.added_at`` — timezone-aware timestamp of when
  the security was added to the watchlist.
- ``market_watchlists_securities.position`` — application-managed manual
  position within the watchlist.

Backfill determinism: existing membership rows carry no ordering information,
so each watchlist's rows are numbered by ``security_id`` ascending
(``row_number() OVER (PARTITION BY watchlist_id ORDER BY security_id)``). This
is arbitrary but stable and reproducible.

Revision ID: 4c2ed77e7738
Revises: 8c982c520acb
Create Date: 2026-09-22 01:02:41.311582

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c2ed77e7738"
down_revision: Union[str, Sequence[str], None] = "8c982c520acb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "market_watchlists",
        sa.Column("sort", sa.String(), server_default="custom", nullable=True),
    )
    op.add_column(
        "market_watchlists_securities",
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.add_column(
        "market_watchlists_securities",
        sa.Column("position", sa.Integer(), nullable=True),
    )

    # Backfill existing rows before enforcing NOT NULL.
    op.execute("UPDATE market_watchlists SET sort = 'custom' WHERE sort IS NULL")
    op.execute(
        "UPDATE market_watchlists_securities "
        "SET added_at = now() WHERE added_at IS NULL"
    )
    op.execute(
        "UPDATE market_watchlists_securities AS mws "
        "SET position = numbered.position "
        "FROM ("
        "  SELECT watchlist_id, security_id, "
        "         row_number() OVER ("
        "           PARTITION BY watchlist_id ORDER BY security_id"
        "         ) AS position "
        "  FROM market_watchlists_securities"
        ") AS numbered "
        "WHERE mws.watchlist_id = numbered.watchlist_id "
        "  AND mws.security_id = numbered.security_id"
    )

    op.alter_column("market_watchlists", "sort", nullable=False)
    op.alter_column("market_watchlists_securities", "added_at", nullable=False)
    op.alter_column("market_watchlists_securities", "position", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("market_watchlists_securities", "position")
    op.drop_column("market_watchlists_securities", "added_at")
    op.drop_column("market_watchlists", "sort")
