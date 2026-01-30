from abc import ABC, abstractmethod

from src.account.api_types import InstitutionEnum
from src.auth.api_types import UserId
from src.integration.api_types import IntegrationUserId
from src.integration.schema import IntegrationUserSchema


class IntegrationUserRepository(ABC):
    @abstractmethod
    async def create(
        self, integration_user: IntegrationUserSchema
    ) -> IntegrationUserSchema:
        pass

    @abstractmethod
    async def get(
        self, integration_user_id: IntegrationUserId
    ) -> IntegrationUserSchema | None:
        pass

    @abstractmethod
    async def get_by_user_and_institution(
        self, user_id: UserId, institution: InstitutionEnum
    ) -> list[IntegrationUserSchema]:
        pass

    @abstractmethod
    async def get_unique(
        self, user_id: UserId, institution: InstitutionEnum, username: str
    ) -> IntegrationUserSchema | None:
        pass

    @abstractmethod
    async def exists(
        self, user_id: UserId, institution: InstitutionEnum, username: str
    ) -> bool:
        pass

    @abstractmethod
    async def update_last_used_at(
        self, integration_user: IntegrationUserSchema
    ) -> None:
        pass
