"""drop_market_indicator_preferences_table

Revision ID: 65b4bef42c13
Revises: 
Create Date: 2026-08-07 01:16:54.336005

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65b4bef42c13'
down_revision: Union[str, Sequence[str], None] = "1548d7b88af5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the per-security indicator preferences table."""
    op.drop_table("market_indicator_preferences")


def downgrade() -> None:
    """Recreate the per-security indicator preferences table."""
    op.create_table(
        "market_indicator_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("indicators_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["security_id"], ["market_securities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id", "user_id", name="indicator_prefs_unique"
        ),
    )
