from abc import ABC, abstractmethod

import keyring
from keyrings.alt.file import PlaintextKeyring
from svcs import Container

from src.enums import InstitutionEnum
from src.repositories.account import AccountRepository
from src.repositories.account_type import AccountTypeRepository
from src.repositories.position import PositionRepository
from src.repositories.security import SecurityRepository
from src.schemas import Account, FullExternalUser, Position


class ExternalAPIWrapper(ABC):
    _keyring_prefix: str
    _institution: InstitutionEnum

    _account_repository: AccountRepository
    _account_type_repository: AccountTypeRepository
    _position_repository: PositionRepository
    _security_repository: SecurityRepository

    def __init__(
        self,
        account_repository: AccountRepository,
        account_type_repository: AccountTypeRepository,
        position_repository: PositionRepository,
        security_repository: SecurityRepository,
    ):
        self._account_repository = account_repository
        self._account_type_repository = account_type_repository
        self._position_repository = position_repository
        self._security_repository = security_repository

        keyring.set_keyring(PlaintextKeyring())

    @abstractmethod
    def login(
        self,
        username: str,
        password: str | None = None,
        otp: str | None = None,
    ) -> bool:
        pass

    @abstractmethod
    async def import_accounts(
        self, external_user: FullExternalUser, account_ids: list[str] | None = None
    ) -> list[Account]:
        pass

    @abstractmethod
    async def import_positions(
        self, external_user: FullExternalUser, account: Account
    ) -> list[Position]:
        pass
