from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from stockholm import Currency, Money

from src.auth.api_types import UserId
from src.core.enum import AccountTypeEnum, InstitutionEnum
from src.market.api_types import SecurityId

type AccountId = UUID
type PositionId = int
type PortfolioId = UUID


class Account(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: AccountId
    external_id: str
    name: str
    user_id: UserId
    integration_user_id: UUID | None = None
    account_type_id: AccountTypeEnum
    institution_id: int
    currency: Currency
    broker_display_name: str | None = None
    is_active: bool = True
    last_sync_at: datetime | None = None


class Position(BaseModel):
    id: PositionId | None = None
    account_id: AccountId
    security_id: SecurityId
    quantity: Decimal
    average_cost: Decimal | None
    currency: str | None = None


class AccountTotals(BaseModel):
    cost: Money
    value: Money


class AccountRenameRequest(BaseModel):
    name: str


class Institution(BaseModel):
    id: InstitutionEnum
    name: str
    country: str
    website: str | None
    is_active: bool
    integration_enabled: bool


class UserPreferences(BaseModel):
    """Permissive user chart preferences — server passes through."""

    timeframe: str | None = None
    chart_style: str | None = None
    indicators: dict[str, Any] | None = None
    sidebar_open: bool | None = None
    holdings_period: str | None = None
    elliott_waves: dict[str, Any] | None = None
    fibonacci_tools: dict[str, Any] | None = None
    wave_settings: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")
