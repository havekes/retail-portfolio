"""create_security_valuations

Revision ID: 3436586a755f
Revises: 4c2ed77e7738
Create Date: 2026-09-26 20:11:45.881855

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3436586a755f'
down_revision: Union[str, Sequence[str], None] = '4c2ed77e7738'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'market_security_valuations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('security_id', sa.Uuid(), nullable=False),
        sa.Column('lower_bound', sa.DECIMAL(precision=16, scale=8), nullable=False),
        sa.Column('upper_bound', sa.DECIMAL(precision=16, scale=8), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['security_id'], ['market_securities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'security_id', name='valuation_user_security_unique'),
    )
    op.create_index(
        'ix_market_security_valuations_user_security',
        'market_security_valuations',
        ['user_id', 'security_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_market_security_valuations_user_security', table_name='market_security_valuations')
    op.drop_table('market_security_valuations')

