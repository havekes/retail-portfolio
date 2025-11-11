"""Rename tables to plural

Revision ID: 86d6e41b7b07
Revises: 57a42e499ef3
Create Date: 2025-11-10 17:32:57.199868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86d6e41b7b07'
down_revision: Union[str, Sequence[str], None] = '57a42e499ef3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename tables to plural
    op.rename_table('user', 'users')
    op.rename_table('account_type', 'account_types')
    op.rename_table('institution', 'institutions')
    op.rename_table('ticker', 'tickers')
    op.rename_table('account', 'accounts')
    op.rename_table('action_item', 'action_items')
    op.rename_table('reminder', 'reminders')
    op.rename_table('watchlist', 'watchlists')
    op.rename_table('note', 'notes')
    op.rename_table('watchlist_item', 'watchlist_items')


def downgrade() -> None:
    """Downgrade schema."""
    # Rename tables back to singular
    op.rename_table('watchlist_items', 'watchlist_item')
    op.rename_table('notes', 'note')
    op.rename_table('watchlists', 'watchlist')
    op.rename_table('reminders', 'reminder')
    op.rename_table('action_items', 'action_item')
    op.rename_table('accounts', 'account')
    op.rename_table('tickers', 'ticker')
    op.rename_table('institutions', 'institution')
    op.rename_table('account_types', 'account_type')
    op.rename_table('users', 'user')
