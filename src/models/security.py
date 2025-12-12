from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .action_item import ActionItem
    from .note import Note
    from .position import Position
    from .watchlist_item import WatchlistItem


class Security(Base):  # pylint: disable=too-few-public-methods
    """Security model."""

    __tablename__ = "securities"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    sector: Mapped[str] = mapped_column(String, nullable=True)
    industry: Mapped[str] = mapped_column(String, nullable=True)
    market_cap: Mapped[float] = mapped_column(Float)
    pe_ratio: Mapped[float] = mapped_column(Float, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    positions: Mapped[list[Position]] = relationship(
        "Position", back_populates="security", lazy="raise"
    )
    watchlist_items: Mapped[list[WatchlistItem]] = relationship(
        "WatchlistItem", back_populates="security", lazy="raise"
    )
    notes: Mapped[list[Note]] = relationship(
        "Note", back_populates="security", lazy="raise"
    )
    action_items: Mapped[list[ActionItem]] = relationship(
        "ActionItem", back_populates="security", lazy="raise"
    )
