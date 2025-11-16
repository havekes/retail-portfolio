from abc import ABC, abstractmethod
from uuid import UUID

from src.schemas.account import Account


class AccountRepository(ABC):
    @abstractmethod
    async def create_account(self, account: Account) -> Account:
        pass

    @abstractmethod
    async def exists_account_by_user_and_external_id(
        self, user_id: UUID, external_id: str
    ) -> bool:
        pass
