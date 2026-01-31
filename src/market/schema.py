from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict

from src.account.api_types import InstitutionEnum
from src.market.api_types import EodhdSearchResult, HistoricalPrice, SecurityId


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
    id: int | None = None
    institution_id: InstitutionEnum
    broker_symbol: str
    mapped_symbol: str
    broker_exchange: str
    mapped_exchange: str
    broker_name: str
    security_id: SecurityId
    search_results: list[EodhdSearchResult]
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
