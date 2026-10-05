"""add market security valuation history

Revision ID: b291707f24ca
Revises: 7e9699e1590e
Create Date: 2026-10-05 18:47:46.253143

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b291707f24ca'
down_revision: Union[str, Sequence[str], None] = '7e9699e1590e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'market_security_valuation_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('security_id', sa.Uuid(), nullable=False),
        sa.Column('lower_bound', sa.DECIMAL(precision=16, scale=8), nullable=False),
        sa.Column('upper_bound', sa.DECIMAL(precision=16, scale=8), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['security_id'], ['market_securities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_market_security_valuation_history_user_security_created',
        'market_security_valuation_history',
        ['user_id', 'security_id', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'ix_market_security_valuation_history_user_security_created',
        table_name='market_security_valuation_history',
    )
    op.drop_table('market_security_valuation_history')
