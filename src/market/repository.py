from abc import ABC, abstractmethod
from datetime import date

from src.auth.api_types import UserId
from src.market.api_types import SecurityId
from src.market.schema import (
    IndicatorPreferencesRead,
    IndicatorPreferencesWrite,
    PriceAlertRead,
    PriceAlertWrite,
    PriceSchema,
    SecurityBrokerSchema,
    SecurityDocumentRead,
    SecurityDocumentWrite,
    SecurityNoteRead,
    SecurityNoteWrite,
    SecuritySchema,
    WatchlistRead,
)


class SecurityRepository(ABC):
    @abstractmethod
    async def get_by_id_or_fail(self, security_id: SecurityId) -> SecuritySchema:
        pass

    @abstractmethod
    async def get_or_create(self, security: SecuritySchema) -> SecuritySchema:
        pass

    @abstractmethod
    async def get_all_active_securities(self) -> list[SecuritySchema]:
        pass

    @abstractmethod
    async def get_by_code_and_exchange(
        self, code: str, exchange: str
    ) -> SecuritySchema | None:
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
    async def get_by_security(self, security_id: SecurityId) -> list[PriceSchema]:
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
    async def get_by_user(self, user_id: UserId) -> list[WatchlistRead]:
        pass


class PriceAlertRepository(ABC):
    @abstractmethod
    async def get_by_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> list[PriceAlertRead]:
        pass

    @abstractmethod
    async def create(
        self, alert: PriceAlertWrite, security_id: SecurityId, user_id: UserId
    ) -> PriceAlertRead:
        pass

    @abstractmethod
    async def delete(self, alert_id: int, user_id: UserId) -> None:
        pass


class SecurityNoteRepository(ABC):
    @abstractmethod
    async def get_by_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> list[SecurityNoteRead]:
        pass

    @abstractmethod
    async def get_by_id(self, note_id: int) -> SecurityNoteRead | None:
        pass

    @abstractmethod
    async def create(
        self, note: SecurityNoteWrite, security_id: SecurityId, user_id: UserId
    ) -> SecurityNoteRead:
        pass

    @abstractmethod
    async def update(
        self, note_id: int, note: SecurityNoteWrite, user_id: UserId
    ) -> SecurityNoteRead:
        pass

    @abstractmethod
    async def update_title(self, note_id: int, title: str) -> None:
        pass

    @abstractmethod
    async def delete(self, note_id: int, user_id: UserId) -> None:
        pass


class SecurityDocumentRepository(ABC):
    @abstractmethod
    async def get_by_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> list[SecurityDocumentRead]:
        pass

    @abstractmethod
    async def create(
        self,
        document: SecurityDocumentWrite,
        security_id: SecurityId,
        user_id: UserId,
    ) -> SecurityDocumentRead:
        pass

    @abstractmethod
    async def delete(self, document_id: int, user_id: UserId) -> None:
        pass


class IndicatorPreferencesRepository(ABC):
    @abstractmethod
    async def get_for_security_and_user(
        self, security_id: SecurityId, user_id: UserId
    ) -> IndicatorPreferencesRead | None:
        pass

    @abstractmethod
    async def save(
        self,
        preferences: IndicatorPreferencesWrite,
        security_id: SecurityId,
        user_id: UserId,
    ) -> IndicatorPreferencesRead:
        pass
