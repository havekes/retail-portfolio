from enum import IntEnum
from uuid import UUID

from pydantic import BaseModel
from stockholm import Money

type AccountId = UUID
type PositionId = UUID


class InstitutionEnum(IntEnum):
    WEALTHSIMPLE = 1


class AccountTypeEnum(IntEnum):
    TFSA = 1
    RRSP = 2
    FHSA = 3
    NON_REGISTERED = 4


class AccountTotals(BaseModel):
    cost: Money
    price: Money


class AccountRenameRequest(BaseModel):
    name: str
