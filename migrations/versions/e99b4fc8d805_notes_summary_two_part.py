"""notes summary two part

Replaces the single ``summary`` column on ``market_security_note_summaries``
with the two-part shape (``short_summary`` <=160 chars, ``long_summary``).

Both new columns are added nullable, backfilled from the old ``summary``
(the old text becomes ``long_summary``, a derived first-sentence digest becomes
``short_summary``), and only then set NOT NULL — so existing rows survive
without a server-side default. The FK CASCADE and the
``UniqueConstraint('security_id', 'user_id')`` are untouched by the column swap.

The downgrade reassembles ``summary`` from ``long_summary``.

Revision ID: e99b4fc8d805
Revises: 3909e15d1793
Create Date: 2026-09-22 19:29:53.788976

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e99b4fc8d805"
down_revision: Union[str, Sequence[str], None] = "3909e15d1793"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Derive the short digest from the old full summary: take leading sentences
# until adding the next one would exceed 160 chars, then hard-truncate. Mirrors
# the app-layer ``AIService._derive_short_summary`` fallback.
_BACKFILL_SHORT_SUMMARY = """
UPDATE market_security_note_summaries
SET short_summary = CASE
    WHEN length(btrim(regexp_replace(summary, '\\s+', ' ', 'g'))) <= 160
        THEN btrim(regexp_replace(summary, '\\s+', ' ', 'g'))
    WHEN length(btrim((regexp_match(btrim(regexp_replace(summary, '\\s+', ' ', 'g')), '^.{1,160}(?:[.!?](?=\\s|$)|(?=\\s|$))'))[1])) > 0
        THEN btrim((regexp_match(btrim(regexp_replace(summary, '\\s+', ' ', 'g')), '^.{1,160}(?:[.!?](?=\\s|$)|(?=\\s|$))'))[1])
    ELSE left(btrim(regexp_replace(summary, '\\s+', ' ', 'g')), 160)
END
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Add nullable first so the NOT NULL columns can be backfilled from `summary`.
    op.add_column(
        "market_security_note_summaries",
        sa.Column("short_summary", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "market_security_note_summaries",
        sa.Column("long_summary", sa.Text(), nullable=True),
    )

    # Old single-volume summary becomes the paragraph; a truncated digest is
    # derived for the short part.
    op.execute(
        "UPDATE market_security_note_summaries "
        "SET long_summary = summary, short_summary = left(summary, 160)"
    )
    op.execute(_BACKFILL_SHORT_SUMMARY)

    # Any residual NULLs (rows with an empty/NULL summary cannot exist: the old
    # column was NOT NULL, so this is purely defensive) get a placeholder before
    # the NOT NULL constraint lands.
    op.execute(
        "UPDATE market_security_note_summaries "
        "SET short_summary = COALESCE(short_summary, ''), "
        "long_summary = COALESCE(long_summary, '')"
    )

    op.alter_column(
        "market_security_note_summaries",
        "short_summary",
        existing_type=sa.String(length=160),
        nullable=False,
    )
    op.alter_column(
        "market_security_note_summaries",
        "long_summary",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column("market_security_note_summaries", "summary")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "market_security_note_summaries",
        sa.Column("summary", sa.VARCHAR(), nullable=True),
    )

    # Prefer the paragraph when reassembling the old single-volume summary.
    op.execute("UPDATE market_security_note_summaries SET summary = long_summary")
    op.execute(
        "UPDATE market_security_note_summaries "
        "SET summary = COALESCE(summary, short_summary, '')"
    )

    op.alter_column(
        "market_security_note_summaries",
        "summary",
        existing_type=sa.VARCHAR(),
        nullable=False,
    )
    op.drop_column("market_security_note_summaries", "long_summary")
    op.drop_column("market_security_note_summaries", "short_summary")
