"""Seed account types

Revision ID: 886b6490b2e5
Revises: af5f71c37b1d
Create Date: 2025-11-14 18:40:44.440042

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '886b6490b2e5'
down_revision: Union[str, Sequence[str], None] = 'af5f71c37b1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Insert seed data for account_types
    account_types_data = [
        {"id": 1, "name": "TFSA", "country": "CA", "tax_advantaged": True},
        {"id": 2, "name": "RRSP", "country": "CA", "tax_advantaged": True},
        {"id": 3, "name": "RESP", "country": "CA", "tax_advantaged": True},
        {"id": 4, "name": "Non-Registered", "country": "CA", "tax_advantaged": False},
    ]
    op.execute(sa.text("""
        INSERT INTO account_types (name, country, tax_advantaged) VALUES
        ('TFSA', 'CA', true),
        ('RRSP', 'CA', true),
        ('FHSA', 'CA', true),
        ('Non-Registered', 'CA', false)
    """))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove seed data
    op.execute(sa.text("DELETE FROM account_types WHERE id IN (1,2,3,4)"))
