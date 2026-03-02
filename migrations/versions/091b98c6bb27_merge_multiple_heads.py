"""merge multiple heads

Revision ID: 091b98c6bb27
Revises: 0d9b3a153da8, 8db32fd64c78
Create Date: 2026-03-02 03:49:23.257847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '091b98c6bb27'
down_revision: Union[str, Sequence[str], None] = ('0d9b3a153da8', '8db32fd64c78')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
