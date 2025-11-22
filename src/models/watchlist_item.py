from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .security import Security
    from .watchlist import Watchlist


class WatchlistItem(Base):
    """Watchlist item model."""

    __tablename__ = "watchlist_items"

    watchlist_id: Mapped[UUID] = mapped_column(
        ForeignKey("watchlists.id"), primary_key=True
    )
    security_symbol: Mapped[str] = mapped_column(
        ForeignKey("securities.symbol"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now)  # pylint: disable=not-callable

    # Relationships
    watchlist: Mapped[Watchlist] = relationship(
        "Watchlist", back_populates="watchlist_items"
    )
    security: Mapped[Security] = relationship(
        "Security", back_populates="watchlist_items"
    )
