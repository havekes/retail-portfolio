"""add auth totp and recovery codes

Revision ID: 2a86ac6b46ec
Revises: c2a9f7b17e13
Create Date: 2026-08-25 17:42:18.351305

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2a86ac6b46ec'
down_revision: Union[str, Sequence[str], None] = 'c2a9f7b17e13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'auth_totp',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('secret', sa.String(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['auth_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_auth_totp_user_id'), 'auth_totp', ['user_id'], unique=True)
    op.create_table(
        'auth_recovery_codes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('code_hash', sa.String(), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['auth_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_auth_recovery_codes_user_id'), 'auth_recovery_codes', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_auth_recovery_codes_user_id'), table_name='auth_recovery_codes')
    op.drop_table('auth_recovery_codes')
    op.drop_index(op.f('ix_auth_totp_user_id'), table_name='auth_totp')
    op.drop_table('auth_totp')
