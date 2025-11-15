from enum import Enum


class InstitutionEnum(Enum):
    WEALTHSIMPLE = 1


class AccountTypeEnum(Enum):
    TFSA = 1
    RRSP = 2
    FHSA = 3
    NON_REGISTERED = 4
