from decimal import Decimal
from enum import IntEnum
from uuid import UUID

from pydantic import BaseModel
from stockholm import Money

from src.market.api_types import SecurityId

type AccountId = UUID
type PositionId = UUID


class InstitutionEnum(IntEnum):
    WEALTHSIMPLE = 1


class AccountTypeEnum(IntEnum):
    TFSA = 1
    RRSP = 2
    FHSA = 3
    NON_REGISTERED = 4


class Account(BaseModel):
    id: AccountId
    name: str
    user_id: UUID
    account_type_id: AccountTypeEnum
    institution_id: int
    currency: str
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
