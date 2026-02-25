"""add_integration_enabled

Revision ID: 8db32fd64c78
Revises: 7cb8e3038b76
Create Date: 2026-02-18 18:31:33.171134

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8db32fd64c78'
down_revision: Union[str, Sequence[str], None] = '7cb8e3038b76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('account_institutions', sa.Column('integration_enabled', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('account_institutions', 'integration_enabled')
