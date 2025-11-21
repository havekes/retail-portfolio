from abc import ABC, abstractmethod
from uuid import UUID

from src.schemas.position import Position


class PositionRepository(ABC):
    @abstractmethod
    async def create_or_update(self, position: Position) -> Position:
        pass
