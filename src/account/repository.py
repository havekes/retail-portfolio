from abc import ABC, abstractmethod

from src.account.api_types import AccountId, PortfolioId
from src.account.schema import (
    AccountSchema,
    PortfolioCreate,
    PortfolioRead,
    PositionSchema,
)
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


class PortfolioRepository(ABC):
    @abstractmethod
    async def get(self, portfolio_id: PortfolioId) -> PortfolioRead | None:
        pass

    @abstractmethod
    async def get_by_user(self, user_id: UserId) -> list[PortfolioRead]:
        pass

    @abstractmethod
    async def create(
        self, user_id: UserId, portfolio_create: PortfolioCreate
    ) -> PortfolioRead:
        pass

    @abstractmethod
    async def sync_accounts(
        self, portfolio_id: PortfolioId, account_ids: list[AccountId]
    ) -> PortfolioRead:
        pass

    @abstractmethod
    async def delete(self, portfolio_id: PortfolioId) -> None:
        pass
