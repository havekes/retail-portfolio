"""remove_stale_huey_tasks_table

Drops the `huey_tasks` table, which is not part of this project's model
metadata. It is created at runtime by the `huey-dashboard` package
(`TaskDatabase.ensure_table()` runs `metadata.create_all`), which both the
backend (`src/main.py`) and the worker (`src/worker.py`) call on every start —
so migration `673bef7bd9d1_cleanup_schema_drift` already dropped a copy of it,
yet `alembic check` kept reporting it as drift once a process came back up.

The migration is therefore paired with a `huey_tasks` exclusion in
`migrations/env.py`: this revision removes the copy present in existing
databases (idempotently — a fresh database has never seen the table, so
`if_exists` is required for the migration-from-scratch path), and the exclusion
keeps the runtime-owned table out of autogenerate drift for good.

Revision ID: 38f2b955dd04
Revises: b8448ae7dc41
Create Date: 2026-09-22 04:11:23.966901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '38f2b955dd04'
down_revision: Union[str, Sequence[str], None] = 'b8448ae7dc41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Guarded: databases created from migrations alone never have this table
    # (only processes running huey-dashboard create it).
    op.drop_table('huey_tasks', if_exists=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate the minimal shape huey-dashboard expects, but only when the
    # running processes have not already done so.
    bind = op.get_bind()
    if 'huey_tasks' in sa.inspect(bind).get_table_names():
        return
    op.create_table('huey_tasks',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('args', sa.JSON(), nullable=True),
    sa.Column('kwargs', sa.JSON(), nullable=True),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('error', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('huey_tasks_pkey'))
    )
