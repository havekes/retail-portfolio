import uuid
from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict
from stockholm import Currency

from src.account.api_types import (
    AccountId,
    PortfolioId,
    PositionId,
)
from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.auth.api_types import UserId
from src.integration.brokers.api_types import BrokerAccount, BrokerAccountId
from src.market.api_types import SecurityId


class AccountSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: AccountId
    external_id: BrokerAccountId
    name: str
    user_id: UserId
    account_type_id: AccountTypeEnum
    institution_id: InstitutionEnum
    currency: Currency
    is_active: bool = True
    created_at: datetime | None = None
    deleted_at: datetime | None = None

    @classmethod
    def from_broker(cls, broker_account: BrokerAccount, user_id: UserId) -> Self:
        return cls(
            id=uuid.uuid4(),
            external_id=broker_account.id,
            name=broker_account.display_name,
            user_id=user_id,
            account_type_id=broker_account.type,
            institution_id=broker_account.institution,
            currency=broker_account.currency,
        )


class AccountTypeSchema(BaseModel):
    id: AccountTypeEnum
    name: str
    country: str
    tax_advantaged: bool
    is_active: bool


class InstitutionSchema(BaseModel):
    id: InstitutionEnum
    name: str
    country: str
    website: str
    is_active: bool


class PositionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PositionId
    account_id: AccountId
    security_id: SecurityId
    quantity: Decimal
    average_cost: Decimal | None
    updated_at: datetime | None = None


class PositionRead(BaseModel):
    id: PositionId
    account_id: AccountId
    security_id: SecurityId
    security_symbol: str
    quantity: float
    average_cost: float | None
    updated_at: datetime | None = None


class PortfolioAccountSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: AccountId


class PortfolioSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PortfolioId
    user_id: UserId
    name: str
    created_at: datetime | None = None
    deleted_at: datetime | None = None


class PortfolioCreate(BaseModel):
    name: str
    accounts: list[AccountId]


class PortfolioRead(PortfolioSchema):
    accounts: list[AccountSchema]


class PortfolioAccountUpdateRequest(BaseModel):
    accounts: list[AccountId]
