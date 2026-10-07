"""add spousal rrsp account type

Revision ID: e25265d203b2
Revises: b291707f24ca
Create Date: 2026-10-07 00:26:51.136750

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e25265d203b2"
down_revision: Union[str, Sequence[str], None] = "b291707f24ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        INSERT INTO account_types (id, name, country, tax_advantaged, is_active)
        VALUES (5, 'Spousal RRSP', 'CA', true, true)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM account_types WHERE id = 5")
