from abc import ABC, abstractmethod

import keyring
from keyrings.alt.file import PlaintextKeyring
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import InstitutionEnum
from src.repositories.account import AccountRepository
from src.repositories.account_type import AccountTypeRepository
from src.repositories.sqlalchemy_account import SqlAlchemyAccountRepostory
from src.repositories.sqlalchemy_account_type import SqlAlchemyAccountTypeRepository
from src.schemas import Account, User


class ExternalAPIWrapper(ABC):
    _keyring_prefix: str
    _institution: InstitutionEnum

    _session: AsyncSession
    _user: User
    _username: str

    _account_repository: AccountRepository
    _account_type_repository: AccountTypeRepository

    def __init__(self, session: AsyncSession, user: User, username: str):
        self._session = session
        self._user = user
        self._username = username
        self._account_repository = SqlAlchemyAccountRepostory(session)
        self._account_type_repository = SqlAlchemyAccountTypeRepository(session)
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
    async def import_accounts(self) -> list[Account]:
        pass

    @abstractmethod
    async def import_positions(self, account: Account):
        pass
