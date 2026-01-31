from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel
from stockholm.currency import Currency

type SecurityId = UUID


class Security(BaseModel):
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
    ISIN: str
    isPrimary: str
    previousClose: str
    previousCloseDate: str


class HistoricalPrice(BaseModel):
    security_id: SecurityId
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: int
