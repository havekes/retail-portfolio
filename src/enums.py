from enum import Enum, IntEnum


class InstitutionEnum(IntEnum):
    WEALTHSIMPLE = 1


class AccountTypeEnum(IntEnum):
    TFSA = 1
    RRSP = 2
    FHSA = 3
    NON_REGISTERED = 4


class ActionEnum(Enum):
    HOLD = "hold"
    OBSERVE = "observe"
    BUY = "buy"
    SELL = "sell"
