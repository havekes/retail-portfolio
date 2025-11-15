"""Seed institutions

Revision ID: 0c71603756dd
Revises: 886b6490b2e5
Create Date: 2025-11-14 18:40:54.281841

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c71603756dd'
down_revision: Union[str, Sequence[str], None] = '886b6490b2e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Insert seed data for institutions
    op.execute(sa.text("""
        INSERT INTO institutions (id, name, website, country, is_active) VALUES
        (1, 'Wealthsimple', 'https://www.wealthsimple.com', 'CA', true)
    """))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove seed data
    op.execute(sa.text("DELETE FROM institutions WHERE id IN (1)"))
