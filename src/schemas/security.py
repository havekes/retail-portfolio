from pydantic import BaseModel, ConfigDict


class Security(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    market_cap: float
    sector: str | None = None
    industry: str | None = None
    pe_ratio: float | None = None
    is_active: bool = True
