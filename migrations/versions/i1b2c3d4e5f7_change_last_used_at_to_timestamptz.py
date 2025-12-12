"""Change last_used_at to timestamptz

Revision ID: i1b2c3d4e5f7
Revises: f8a9b0c1d2e3
Create Date: 2024-12-19 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE external_users ALTER COLUMN last_used_at TYPE TIMESTAMP WITH TIME ZONE USING last_used_at::timestamp with time zone;")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE external_users ALTER COLUMN last_used_at TYPE DATE USING last_used_at::date;")
