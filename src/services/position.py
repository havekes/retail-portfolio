from collections.abc import AsyncGenerator
from uuid import UUID

from stockholm import Money
from svcs import Container

from src.repositories.position import PositionRepository
from src.schemas import Position
from src.schemas.account import AccountTotals


class PositionService:
    _position_repository: PositionRepository

    def __init__(self, position_repository: PositionRepository):
        self._position_repository = position_repository

    async def get_total_for_account(self, account_id: UUID) -> AccountTotals:
        positions = await self._position_repository.get_by_account(account_id)

        return AccountTotals(cost=self._compute_cost(positions))

    def _compute_cost(self, positions: list[Position]) -> Money:
        return sum(
            (
                round(Money(position.quantity * (position.average_cost or 0), "CAD"), 2)
                for position in positions
            ),
            Money(0),
        )


async def position_service_factory(
    container: Container,
) -> AsyncGenerator[PositionService]:
    yield PositionService(position_repository=await container.aget(PositionRepository))
