from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel
from stockholm import Currency, Money

from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.auth.api_types import UserId
from src.market.api_types import SecurityId

type AccountId = UUID
type PositionId = int
type PortfolioId = UUID


class Account(BaseModel):
    id: AccountId
    name: str
    user_id: UserId
    account_type_id: AccountTypeEnum
    institution_id: int
    currency: Currency
    is_active: bool = True


class Position(BaseModel):
    id: PositionId
    account_id: AccountId
    security_id: SecurityId
    quantity: Decimal
    average_cost: Decimal | None


class AccountTotals(BaseModel):
    cost: Money


class AccountRenameRequest(BaseModel):
    name: str


class Institution(BaseModel):
    id: InstitutionEnum
    name: str
    country: str
    website: str | None
    is_active: bool
    integration_enabled: bool
