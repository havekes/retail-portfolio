import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, field_serializer
from stockholm import Currency

from src.account.api_types import (
    AccountId,
    PortfolioId,
    PositionId,
)
from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.auth.api_types import UserId
from src.integration.api_types import IntegrationUserId
from src.integration.brokers.api_types import BrokerAccount, BrokerAccountId
from src.market.api_types import SecurityId


class AccountSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: AccountId
    external_id: BrokerAccountId
    name: str
    user_id: UserId
    integration_user_id: IntegrationUserId | None = None
    account_type_id: AccountTypeEnum
    institution_id: InstitutionEnum
    currency: Currency
    broker_display_name: str | None = None
    net_deposits: float | None = None
    is_active: bool = True
    created_at: datetime | None = None
    deleted_at: datetime | None = None

    @field_serializer("currency")
    def serialize_currency(self, currency: Currency) -> str:
        return str(currency)

    @classmethod
    def from_broker(
        cls,
        broker_account: BrokerAccount,
        user_id: UserId,
        integration_user_id: IntegrationUserId,
    ) -> Self:
        return cls(
            id=uuid.uuid4(),
            external_id=broker_account.id,
            name=broker_account.display_name,
            user_id=user_id,
            integration_user_id=integration_user_id,
            account_type_id=broker_account.type,
            institution_id=broker_account.institution,
            currency=broker_account.currency,
            broker_display_name=broker_account.broker_display_name,
            net_deposits=(
                float(broker_account.net_deposits)
                if broker_account.net_deposits
                else None
            ),
        )


class AccountTypeSchema(BaseModel):
    id: AccountTypeEnum
    name: str
    country: str
    tax_advantaged: bool
    is_active: bool


class InstitutionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: InstitutionEnum
    name: str
    country: str
    website: str | None
    is_active: bool
    integration_enabled: bool


class PositionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PositionId | None = None
    account_id: AccountId
    security_id: SecurityId
    quantity: Decimal
    average_cost: Decimal | None
    currency: str | None = None
    updated_at: datetime | None = None


class PositionRead(BaseModel):
    id: PositionId
    account_id: AccountId
    security_id: SecurityId
    security_symbol: str
    quantity: float
    average_cost: float | None
    currency: str | None = None
    updated_at: datetime | None = None


class AccountHoldingRead(BaseModel):
    account_id: AccountId
    account_name: str
    quantity: float
    average_cost: float | None = None
    total_value: float
    currency: str


class HoldingRead(BaseModel):
    id: PositionId
    security_id: SecurityId
    security_symbol: str
    security_name: str
    quantity: float
    average_cost: float | None
    total_value: float
    profit_loss: float | None
    currency: str
    security_currency: str
    unconverted_total_value: float
    converted_average_cost: float | None = None
    converted_latest_price: float | None = None
    unconverted_profit_loss: float | None = None
    latest_price: float | None = None
    price_date: date | None = None
    updated_at: datetime | None = None


class AccountHoldingsRead(BaseModel):
    account_id: AccountId
    account_name: str
    holdings: list[HoldingRead]
    total_value: float
    total_profit_loss: float
    total_profit_loss_percent: float | None = None
    net_deposits: float | None = None
    currency: str


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
