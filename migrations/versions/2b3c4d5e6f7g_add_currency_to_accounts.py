"""Add currency column to accounts table

Revision ID: 2b3c4d5e6f7g
Revises: i1b2c3d4e5f7
Create Date: 2024-12-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b3c4d5e6f7g'
down_revision: str = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add currency column
    op.add_column('accounts', sa.Column('currency', sa.String(length=3), server_default='CAD', nullable=True))
    op.alter_column('accounts', 'currency', server_default=None, existing_type=sa.String(length=3), nullable=False)

    # Backfill existing records with 'CAD'
    op.execute("UPDATE accounts SET currency = 'CAD'")

    # Drop the server default now that data is populated
    op.alter_column('accounts', 'currency', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('accounts', 'currency')
