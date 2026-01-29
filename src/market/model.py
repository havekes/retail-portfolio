from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DECIMAL,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from stockholm import Currency


class Base(DeclarativeBase):
    pass


class SecurityModel(Base):  # pylint: disable=too-few-public-methods
    """Security holds generic data about a security"""

    __tablename__ = "market_securities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String)
    exchange: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    isin: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Ensure same symbol cannot exist on same exchange
        # (Allows same symbol on different exchanges, e.g., GOOGL on NASDAQ)
        UniqueConstraint("symbol", "exchange", name="symbol_exchange_unique"),
    )


class PriceModel(Base):
    """Security model."""

    __tablename__ = "market_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("market_securities.id"))
    date: Mapped[date] = mapped_column(Date)
    open: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    high: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    low: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    close: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    adjusted_close: Mapped[Decimal] = mapped_column(DECIMAL(16, 8))
    volume: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[Currency] = mapped_column(String)
