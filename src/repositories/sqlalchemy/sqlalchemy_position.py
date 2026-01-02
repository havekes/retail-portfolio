from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Container

from src.models.position import Position as PositionModel
from src.repositories.position import PositionRepository
from src.schemas.position import Position


class SqlAlchemyPositionRepository(PositionRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_or_update(self, position: Position) -> Position:
        values = position.model_dump(exclude={"id"})
        result = await self._session.execute(
            insert(PositionModel)
            .values(values)
            .on_conflict_do_update(
                index_elements=["account_id", "security_symbol"],
                set_={
                    "quantity": position.quantity,
                    "average_cost": position.average_cost,
                },
            )
            .returning(
                PositionModel.id,
                PositionModel.account_id,
                PositionModel.security_symbol,
                PositionModel.quantity,
                PositionModel.average_cost,
            )
        )
        row_data = result.mappings().first()
        assert row_data is not None
        await self._session.commit()
        return Position.model_validate(dict(row_data))

    async def get_by_account(self, account_id: UUID) -> list[Position]:
        result = await self._session.execute(
            select(PositionModel).where(PositionModel.account_id == account_id)
        )
        positions = result.scalars().all()
        return [Position.model_validate(p) for p in positions]


async def sqlalchemy_position_repository_factory(
    container: Container,
) -> SqlAlchemyPositionRepository:
    return SqlAlchemyPositionRepository(session=await container.aget(AsyncSession))
