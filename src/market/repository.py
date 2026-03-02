from abc import ABC, abstractmethod
from datetime import date

from src.auth.api_types import UserId
from src.market.api_types import SecurityId
from src.market.schema import (
    PriceSchema,
    SecurityBrokerSchema,
    SecuritySchema,
    WatchlistRead,
)


class SecurityRepository(ABC):
    @abstractmethod
    async def get_by_id(self, security_id: SecurityId) -> SecuritySchema:
        pass

    @abstractmethod
    async def get_or_create(self, security: SecuritySchema) -> SecuritySchema:
        pass

    @abstractmethod
    async def get_all_active_securities(self) -> list[SecuritySchema]:
        pass


class SecurityBrokerRepository(ABC):
    @abstractmethod
    async def get_or_create(
        self, security_broker: SecurityBrokerSchema
    ) -> SecurityBrokerSchema:
        pass


class PriceRepository(ABC):
    @abstractmethod
    async def get_prices(
        self, security: SecuritySchema, from_date: date, to_date: date
    ) -> list[PriceSchema]:
        pass

    @abstractmethod
    async def get_latest_price(self, security: SecuritySchema) -> PriceSchema | None:
        pass

    @abstractmethod
    async def get_price_on_date(
        self, security: SecuritySchema, date: date
    ) -> PriceSchema | None:
        pass

    @abstractmethod
    async def save_price(self, price: PriceSchema) -> PriceSchema:
        pass

    @abstractmethod
    async def save_prices(self, prices: list[PriceSchema]) -> list[PriceSchema]:
        pass


class WatchlistRepository(ABC):
    @abstractmethod
    async def get_all_for_user(self, user_id: UserId) -> list[WatchlistRead]:
        pass
