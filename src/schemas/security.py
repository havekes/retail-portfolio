from datetime import datetime

from pydantic import BaseModel


class Security(BaseModel):
    symbol: str
    name: str
    sector: str | None = None
    industry: str | None = None
    market_cap: float
    pe_ratio: float | None = None
    last_updated: datetime
    is_active: bool = True
