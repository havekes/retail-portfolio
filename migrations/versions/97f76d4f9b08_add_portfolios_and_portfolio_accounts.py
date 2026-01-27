"""add_portfolios_and_portfolio_accounts

Revision ID: 97f76d4f9b08
Revises: 2b3c4d5e6f7g
Create Date: 2026-01-27 04:38:54.025870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97f76d4f9b08'
down_revision: Union[str, Sequence[str], None] = '2b3c4d5e6f7g'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create portfolios table
    op.create_table(
        'portfolios',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='fk_portfolios_user_id'),
    )

    # Create portfolio_accounts table
    op.create_table(
        'portfolio_accounts',
        sa.Column('portfolio_id', sa.UUID(), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('portfolio_id', 'account_id'),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='CASCADE', name='fk_portfolio_accounts_portfolio_id'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE', name='fk_portfolio_accounts_account_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('portfolio_accounts')
    op.drop_table('portfolios')
