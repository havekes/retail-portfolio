from abc import ABC, abstractmethod

from src.schemas.security import Security


class SecurityRepository(ABC):
    @abstractmethod
    async def create_or_update(self, security: Security) -> Security:
        pass
