"""Remove current_price from positions

Revision ID: a1b2c3d4e5f6
Revises: i1b2c3d4e5f7
Create Date: 2025-12-12 00:23:51.280566

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Float, DateTime, func, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'i1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'securities',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('sector', sa.String(), nullable=True),
        sa.Column('industry', sa.String(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=False),
        sa.Column('pe_ratio', sa.Float(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    )
    op.create_table(
        'positions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=func.uuid_generate_v4()),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('accounts.id'), nullable=False),
        sa.Column('security_symbol', sa.String(), sa.ForeignKey('securities.symbol'), nullable=False),
        sa.Column('quantity', Float(), nullable=False),
        sa.Column('average_cost', Float(), nullable=False),
        sa.Column('updated_at', DateTime(), server_default=func.now(), onupdate=func.now(), nullable=False),
        UniqueConstraint('account_id', 'security_symbol', name='positions_account_security_uc')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('positions')
    op.drop_table('securities')
