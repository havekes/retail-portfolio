from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict

from src.account.enum import InstitutionEnum
from src.auth.api_types import UserId
from src.market.api_types import (
    HistoricalPrice,
    Price,
    SecurityId,
    SecuritySearchResult,
    WatchlistId,
)


class SecuritySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: SecurityId
    symbol: str
    exchange: str
    currency: str
    name: str
    isin: str | None
    is_active: bool = True
    updated_at: datetime

    def get_eodhd_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


class SecurityBrokerSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    institution_id: InstitutionEnum
    broker_symbol: str
    mapped_symbol: str
    broker_exchange: str
    mapped_exchange: str
    broker_name: str
    security_id: SecurityId
    search_results: list[SecuritySearchResult]
    created_at: datetime | None = None


class PriceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    security_id: SecurityId
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: int

    @classmethod
    def from_historical_price(cls, historical_price: HistoricalPrice) -> Self:
        return cls(
            security_id=historical_price.security_id,
            date=historical_price.date,
            open=historical_price.open,
            high=historical_price.high,
            low=historical_price.low,
            close=historical_price.close,
            adjusted_close=historical_price.adjusted_close,
            volume=historical_price.volume,
        )


class WatchlistSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: WatchlistId
    user_id: UserId
    name: str


class WatchlistRead(WatchlistSchema):
    securities: list[SecuritySchema]


class PriceHistoryRead(BaseModel):
    """Response schema for price history endpoint."""

    security_id: SecurityId
    from_date: date
    to_date: date
    prices: list[PriceSchema]


class SecurityCreateRequest(BaseModel):
    """Request schema for creating a security from search results."""

    code: str
    exchange: str
    name: str
    currency: str
    isin: str | None = None


class SecurityCreateResponse(BaseModel):
    """Response schema for security creation endpoint."""

    model_config = ConfigDict(from_attributes=True)

    security_id: SecurityId
    symbol: str
    exchange: str
    name: str
    has_price_data: bool


class PriceAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    security_id: SecurityId
    user_id: UserId
    target_price: Decimal
    condition: str
    triggered_at: datetime | None
    created_at: datetime


class PriceAlertWrite(BaseModel):
    target_price: Decimal
    condition: str


class SecurityNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    security_id: SecurityId
    user_id: UserId
    title: str | None = None
    content: str
    created_at: datetime
    updated_at: datetime


class SecurityNoteWrite(BaseModel):
    title: str | None = None
    content: str


class SecurityDocumentWrite(BaseModel):
    filename: str
    file_path: str
    file_size: int
    file_type: str


class SecurityDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    security_id: SecurityId
    user_id: UserId
    filename: str
    file_path: str
    file_size: int
    file_type: str
    created_at: datetime


class IndicatorPreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    security_id: SecurityId
    user_id: UserId
    indicators_json: dict
    updated_at: datetime


class IndicatorPreferencesWrite(BaseModel):
    indicators_json: dict


class MAPoint(BaseModel):
    date: date
    value: float


class MACDPoint(BaseModel):
    date: date
    macd: float
    signal: float
    histogram: float


class RSIPoint(BaseModel):
    date: date
    rsi: float


class TechnicalIndicatorsRead(BaseModel):
    security_id: SecurityId
    ma_50_day: list[MAPoint] | None = None
    ma_200_day: list[MAPoint] | None = None
    ma_50_week: list[MAPoint] | None = None
    ma_200_week: list[MAPoint] | None = None
    macd: list[MACDPoint] | None = None
    rsi: list[RSIPoint] | None = None


class AIAnalysisRequest(BaseModel):
    portfolio_context: str | None = None


class AIAnalysisResponse(BaseModel):
    content: str
    generated_at: str
