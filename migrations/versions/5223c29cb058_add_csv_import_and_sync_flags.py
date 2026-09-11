"""add_csv_import_and_sync_flags

Revision ID: 5223c29cb058
Revises: bea77d72aaf1
Create Date: 2026-09-11 20:44:11.608107

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5223c29cb058'
down_revision: Union[str, Sequence[str], None] = 'bea77d72aaf1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "accounts",
        sa.Column(
            "api_sync_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "account_institutions",
        sa.Column(
            "csv_import_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "account_institutions",
        sa.Column("csv_format", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("account_institutions", "csv_format")
    op.drop_column("account_institutions", "csv_import_enabled")
    op.drop_column("accounts", "api_sync_enabled")

