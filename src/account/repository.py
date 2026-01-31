from abc import ABC, abstractmethod

from src.account.api_types import AccountId
from src.account.schema import AccountSchema, PositionSchema
from src.auth.api_types import UserId
from src.integration.brokers.api_types import BrokerAccountId


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
    async def exists_by_user_and_broker_id(
        self, user_id: UserId, broker_id: BrokerAccountId
    ) -> bool:
        pass

    @abstractmethod
    async def get_by_user(self, user_id: UserId) -> list[AccountSchema]:
        pass


class PositionRepository(ABC):
    @abstractmethod
    async def get_by_account(self, account_id: AccountId) -> list[PositionSchema]:
        pass
