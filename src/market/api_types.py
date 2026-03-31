from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from stockholm.currency import Currency

type SecurityId = UUID
type WatchlistId = UUID


class Security(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: SecurityId
    symbol: str
    exchange: str
    currency: Currency
    name: str
    isin: str | None
    is_active: bool
    updated_at: datetime


class Price(BaseModel):
    id: int
    security_id: int
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: Decimal
    currency: Currency


class EodhdSearchResult(TypedDict):
    Code: str
    Currency: str
    Exchange: str
    Name: str
    Type: str
    Country: str
    ISIN: str | None
    isPrimary: bool
    previousClose: float
    previousCloseDate: str


class HistoricalPrice(BaseModel):
    id: int | None = None
    security_id: SecurityId
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: int


class SecuritySearchResult(BaseModel):
    """Public-facing security search result."""

    code: str
    exchange: str
    name: str
    currency: str
    security_type: str
    isin: str | None
    country: str
