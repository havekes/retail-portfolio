from enum import IntEnum


class InstitutionEnum(IntEnum):
    WEALTHSIMPLE = 1
    QUESTRADE = 2


class AccountTypeEnum(IntEnum):
    TFSA = 1
    RRSP = 2
    FHSA = 3
    NON_REGISTERED = 4
