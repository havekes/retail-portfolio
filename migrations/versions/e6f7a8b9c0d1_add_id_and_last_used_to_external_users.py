"""Add id as UUID primary key and last_used_at to external_users

Revision ID: e6f7a8b9c0d1
Revises: cc62b34f7996
Create Date: 2024-12-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'cc62b34f7996'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the new id column with default UUID
    op.add_column('external_users', sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False))
    # Add last_used_at column
    op.add_column('external_users', sa.Column('last_used_at', sa.Date(), nullable=True))
    # Drop the existing primary key constraint
    op.drop_constraint('external_users_pkey', 'external_users', type_='primary')
    # Create new primary key on id
    op.create_primary_key('external_users_pkey', 'external_users', ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the new primary key
    op.drop_constraint('external_users_pkey', 'external_users', type_='primary')
    # Recreate the old primary key on user_id, institution_id, external_user_id
    op.create_primary_key('external_users_pkey', 'external_users', ['user_id', 'institution_id', 'external_user_id'])
    # Drop the new columns
    op.drop_column('external_users', 'last_used_at')
    op.drop_column('external_users', 'id')
