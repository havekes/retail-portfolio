from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.core.enum import AccountTypeEnum


class CsvPositionRecord(BaseModel):
    """Parsed position record from CSV."""

    model_config = ConfigDict(from_attributes=True)

    symbol: str
    exchange: str | None = None
    name: str | None = None
    quantity: Decimal
    average_cost: Decimal | None = None
    currency: str


class CsvDiscoveredAccount(BaseModel):
    """Discovered account with metadata and position preview."""

    model_config = ConfigDict(from_attributes=True)

    account_number: str
    account_name: str
    account_type_id: AccountTypeEnum
    account_type_name: str
    currency: str
    positions_count: int
    positions: list[CsvPositionRecord] = Field(default_factory=list)
