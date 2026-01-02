from abc import ABC, abstractmethod

from src.schemas.security import Security


class SecurityRepository(ABC):
    @abstractmethod
    async def get_or_create(self, security: Security) -> Security:
        pass
