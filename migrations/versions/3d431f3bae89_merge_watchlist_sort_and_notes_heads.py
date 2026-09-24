"""merge watchlist sort and notes heads

Revision ID: 3d431f3bae89
Revises: 38f2b955dd04, 4c2ed77e7738
Create Date: 2026-09-22 16:20:45.413268

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d431f3bae89'
down_revision: Union[str, Sequence[str], None] = ('38f2b955dd04', '4c2ed77e7738')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
