from abc import ABC, abstractmethod
from uuid import UUID

from src.account.api_types import AccountId
from src.account.schema import AccountSchema, PositionSchema


class AccountRepository(ABC):
    @abstractmethod
    async def get(self, account_id: AccountId) -> AccountSchema | None:
        pass

    @abstractmethod
    async def create(self, account: AccountSchema) -> AccountSchema:
        pass

    @abstractmethod
    async def rename(self, account_id: AccountId, new_name: str) -> AccountSchema:
        pass

    @abstractmethod
    async def exists_by_user_and_external_id(
        self, user_id: UUID, external_id: str
    ) -> bool:
        pass

    @abstractmethod
    async def get_by_user(self, user_id: UUID) -> list[AccountSchema]:
        pass


class PositionRepository(ABC):
    @abstractmethod
    async def get_by_account(self, account_id: AccountId) -> list[PositionSchema]:
        pass
