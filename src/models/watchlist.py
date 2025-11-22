from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .user import User
    from .watchlist_item import WatchlistItem


class Watchlist(Base):
    """Watchlist model."""

    __tablename__ = "watchlists"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String, default="Main Watchlist")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now)  # pylint: disable=not-callable

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="watchlists")
    watchlist_items: Mapped[list[WatchlistItem]] = relationship(
        "WatchlistItem", back_populates="watchlist"
    )
