from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Security(BaseModel):
    symbol: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: float
    pe_ratio: Optional[float] = None
    last_updated: datetime
    is_active: bool = True
