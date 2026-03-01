"""merge heads

Revision ID: 4bc783100e62
Revises: 0d9b3a153da8, 8db32fd64c78
Create Date: 2026-03-01 15:49:22.332998

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4bc783100e62'
down_revision: Union[str, Sequence[str], None] = ('0d9b3a153da8', '8db32fd64c78')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
