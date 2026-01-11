from abc import ABC, abstractmethod
from uuid import UUID

from src.schemas.account import Account


class AccountRepository(ABC):
    @abstractmethod
    async def get(self, account_id: UUID) -> Account | None:
        pass

    @abstractmethod
    async def create_account(self, account: Account) -> Account:
        pass

    @abstractmethod
    async def exists_by_user_and_external_id(
        self, user_id: UUID, external_id: str
    ) -> bool:
        pass

    @abstractmethod
    async def get_by_user(self, user_id: UUID) -> list[Account]:
        pass

    @abstractmethod
    async def rename(self, account_id: UUID, new_name: str) -> Account:
        pass
