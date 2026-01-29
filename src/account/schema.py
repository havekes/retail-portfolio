from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.account.api_types import (
    AccountId,
    AccountTypeEnum,
    InstitutionEnum,
    PositionId,
)
from src.market.api_types import SecurityId


class AccountSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: AccountId
    external_id: str
    name: str
    user_id: UUID
    account_type_id: AccountTypeEnum
    institution_id: int
    currency: str
    is_active: bool = True
    created_at: datetime | None = None
    deleted_at: datetime | None = None


class AccountType(BaseModel):
    id: AccountTypeEnum
    name: str
    country: str
    tax_advantaged: bool
    is_active: bool


class Institution(BaseModel):
    id: InstitutionEnum
    name: str
    country: str
    website: str
    is_active: bool


class Position(BaseModel):
    id: PositionId
    account_id: AccountId
    security_id: SecurityId
    quantity: Decimal
    average_cost: Decimal | None
    updated_at: datetime
