import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from stockholm import Currency

from src.account.api_types import AccountId, Position
from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.market.api_types import SecurityId

type BrokerAccountId = str
type BrokerUserId = str


class BrokerAccount(BaseModel):
    id: BrokerAccountId
    type: AccountTypeEnum
    institution: InstitutionEnum
    currency: Currency
    display_name: str
    value: Decimal
    created_at: datetime


class BrokerPosition(BaseModel):
    broker_account_id: BrokerAccountId
    name: str
    symbol: str
    exchange: str
    quantity: Decimal
    average_cost: Decimal | None

    def to_position(
        self,
        account_id: AccountId,
        security_id: SecurityId,
    ) -> Position:
        return Position(
            id=uuid.uuid4(),
            account_id=account_id,
            security_id=security_id,
            quantity=self.quantity,
            average_cost=self.average_cost,
        )
