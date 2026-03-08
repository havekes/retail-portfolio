"""merge heads

Revision ID: a69a19f736fa
Revises: f12148279f9f, caedf9ddc2ab
Create Date: 2026-03-08 01:09:33.402959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a69a19f736fa'
down_revision: Union[str, Sequence[str], None] = ('f12148279f9f', 'caedf9ddc2ab')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
