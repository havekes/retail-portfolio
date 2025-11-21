"""Add external_users table

Revision ID: cc62b34f7996
Revises: 0c71603756dd
Create Date: 2025-11-17 08:31:19.285563

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc62b34f7996'
down_revision: Union[str, Sequence[str], None] = '0c71603756dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "external_users",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("external_user_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.PrimaryKeyConstraint("user_id", "institution_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("external_users")
