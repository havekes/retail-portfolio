from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.position import Position as PositionModel
from src.repositories.position import PositionRepository
from src.schemas.position import Position


class SqlAlchemyPositionRepository(PositionRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_or_update(self, position: Position) -> Position:
        pass
