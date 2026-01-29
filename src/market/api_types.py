from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from stockholm.currency import Currency

type SecurityId = UUID


class Security(BaseModel):
    id: UUID
    symbol: str
    exchange: str
    currency: Currency
    name: str
    isin: str | None
    is_active: bool
    updated_at: datetime
