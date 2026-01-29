from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from stockholm import Currency


class SecuritySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    symbol: str
    exchange: str
    currency: str
    name: str
    isin: str | None
    is_active: bool = True
    updated_at: datetime

    def get_eodhd_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


class SecurityWrite(BaseModel):
    symbol: str
    exchange: str
    currency: str
    name: str
    isin: str | None
    market_cap: float
    is_active: bool = True


class PriceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None
    security_id: int
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: Decimal
    currency: Currency
