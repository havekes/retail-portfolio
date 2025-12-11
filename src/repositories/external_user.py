from abc import ABC, abstractmethod
from uuid import UUID

from src.schemas.external_user import FullExternalUser


class ExternalUserRepository(ABC):
    @abstractmethod
    async def create(self, external_user: FullExternalUser) -> FullExternalUser:
        pass

    @abstractmethod
    async def get(self, external_user_id: UUID) -> FullExternalUser | None:
        pass

    @abstractmethod
    async def get_by_user_and_institution(
        self, user_id: UUID, institution_id: int
    ) -> list[FullExternalUser]:
        pass

    @abstractmethod
    async def get_unique(
        self, user_id: UUID, institution_id: int, username: str
    ) -> FullExternalUser | None:
        pass

    @abstractmethod
    async def exists(self, user_id: UUID, institution_id: int, username: str) -> bool:
        pass
