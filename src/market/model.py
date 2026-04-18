from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    DECIMAL,
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.auth.api_types import UserId
from src.config.database import BaseModel
from src.market.api_types import EodhdSearchResult, SecurityId, WatchlistId


class SecurityModel(BaseModel):  # pylint: disable=too-few-public-methods
    """Security holds generic data about a security"""

    __tablename__ = "market_securities"

    id: Mapped[SecurityId] = mapped_column(Uuid, primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String)
    exchange: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    isin: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Ensure same symbol cannot exist on same exchange
        # (Allows same symbol on different exchanges, e.g., GOOGL on NASDAQ)
        UniqueConstraint("symbol", "exchange", name="symbol_exchange_unique"),
    )


class SecurityBrokerModel(BaseModel):
    __tablename__ = "market_securities_broker"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    institution_id: Mapped[int] = mapped_column(Integer)
    broker_symbol: Mapped[str] = mapped_column(String)
    broker_exchange: Mapped[str] = mapped_column(String)
    broker_name: Mapped[str] = mapped_column(String)
    mapped_symbol: Mapped[str] = mapped_column(String)
    mapped_exchange: Mapped[str] = mapped_column(String)
    security_id: Mapped[SecurityId] = mapped_column(
        Uuid, ForeignKey("market_securities.id")
    )
    search_results: Mapped[list[EodhdSearchResult]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )


class PriceModel(BaseModel):
    """Security model."""

    __tablename__ = "market_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    security_id: Mapped[SecurityId] = mapped_column(
        Uuid, ForeignKey("market_securities.id")
    )
    date: Mapped[dt_date] = mapped_column(Date)
    open: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    high: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    low: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    close: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    adjusted_close: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    volume: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (
        UniqueConstraint("security_id", "date", name="price_security_date_unique"),
    )


class WatchlistsSecuritiesModel(BaseModel):
    __tablename__ = "market_watchlists_securities"

    watchlist_id: Mapped[WatchlistId] = mapped_column(
        Uuid, ForeignKey("market_watchlists.id", ondelete="CASCADE"), primary_key=True
    )
    security_id: Mapped[SecurityId] = mapped_column(
        Uuid, ForeignKey("market_securities.id", ondelete="CASCADE"), primary_key=True
    )


class WatchlistModel(BaseModel):
    __tablename__ = "market_watchlists"

    id: Mapped[WatchlistId] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UserId] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(String)

    securities: Mapped[list[SecurityModel]] = relationship(
        secondary="market_watchlists_securities",
        lazy="selectin",
    )


class PriceAlertModel(BaseModel):
    __tablename__ = "market_price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    security_id: Mapped[SecurityId] = mapped_column(
        Uuid, ForeignKey("market_securities.id", ondelete="CASCADE")
    )
    user_id: Mapped[UserId] = mapped_column(Uuid)
    target_price: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    condition: Mapped[str] = mapped_column(String)
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )


class SecurityNoteModel(BaseModel):
    __tablename__ = "market_security_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    security_id: Mapped[SecurityId] = mapped_column(
        Uuid, ForeignKey("market_securities.id", ondelete="CASCADE")
    )
    user_id: Mapped[UserId] = mapped_column(Uuid)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )


class SecurityDocumentModel(BaseModel):
    __tablename__ = "market_security_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    security_id: Mapped[SecurityId] = mapped_column(
        Uuid, ForeignKey("market_securities.id", ondelete="CASCADE")
    )
    user_id: Mapped[UserId] = mapped_column(Uuid)
    filename: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    file_size: Mapped[int] = mapped_column(Integer)
    file_type: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )


class IndicatorPreferencesModel(BaseModel):
    __tablename__ = "market_indicator_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    security_id: Mapped[SecurityId] = mapped_column(
        Uuid, ForeignKey("market_securities.id", ondelete="CASCADE")
    )
    user_id: Mapped[UserId] = mapped_column(Uuid)
    indicators_json: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("security_id", "user_id", name="indicator_prefs_unique"),
    )
