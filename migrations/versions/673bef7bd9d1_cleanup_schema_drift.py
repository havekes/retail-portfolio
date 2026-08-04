"""cleanup_schema_drift

Reconciliation migration — drops orphaned `huey_tasks` table and widens 8
non-tz timestamp columns to `DateTime(timezone=True)` interpreting existing
naive values as UTC via `AT TIME ZONE 'UTC'`.

Huey no longer uses SQL storage: the worker uses `RedisHueyWithRegistry`
in production and `MemoryHueyWithRegistry` in tests (no SQL storage
backend exists in `src/`). The orphaned table is a leftover from an
earlier Huey configuration.

Residual drift between the models and the migration history was spotted
via `alembic revision --autogenerate` after migration 4d2535bc952f.

The `watchlist_user_name_unique` drift previously emitted by autogenerate
was an artifact of incomplete metadata (the `WatchlistModel` was not
imported in `migrations/env.py`); it vanishes once all model modules are
imported, and migration `75fd69f81a15` already creates that constraint —
so no `op.create_unique_constraint` is emitted here.

Revision ID: 673bef7bd9d1
Revises: 4d2535bc952f
Create Date: 2026-08-04 02:33:34.467445

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "673bef7bd9d1"
down_revision: Union[str, Sequence[str], None] = "4d2535bc952f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop orphaned Huey SQL-storage table
    op.drop_table("huey_tasks", if_exists=True)

    # accounts
    op.alter_column(
        "accounts",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )
    op.alter_column(
        "accounts",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )
    op.alter_column(
        "accounts",
        "deleted_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="deleted_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )
    op.alter_column(
        "accounts",
        "last_sync_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="last_sync_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )

    # portfolios
    op.alter_column(
        "portfolios",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )
    op.alter_column(
        "portfolios",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )
    op.alter_column(
        "portfolios",
        "deleted_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="deleted_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )

    # portfolio_accounts
    op.alter_column(
        "portfolio_accounts",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse alter_column ops (reverse order)
    # portfolio_accounts
    op.alter_column(
        "portfolio_accounts",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )

    # portfolios
    op.alter_column(
        "portfolios",
        "deleted_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        postgresql_using="deleted_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )
    op.alter_column(
        "portfolios",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )
    op.alter_column(
        "portfolios",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )

    # accounts
    op.alter_column(
        "accounts",
        "last_sync_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        postgresql_using="last_sync_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )
    op.alter_column(
        "accounts",
        "deleted_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        postgresql_using="deleted_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )
    op.alter_column(
        "accounts",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )
    op.alter_column(
        "accounts",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
        existing_nullable=False,
    )

    # no-op: orphaned Huey SQL-storage table, intentionally not recreated
    # (Huey uses Redis)
