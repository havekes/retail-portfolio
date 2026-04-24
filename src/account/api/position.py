from svcs import Container

from src.account.api_types import AccountId, Position
from src.account.repository import PositionRepository
from src.account.schema import PositionSchema


class PositionApi:
    _position_repository: PositionRepository

    def __init__(self, position_repository: PositionRepository) -> None:
        self._position_repository = position_repository

    async def create(self, positions: list[Position]) -> list[Position]:
        """Create new positions. Groups by account and syncs."""
        accounts_positions: dict[AccountId, list[Position]] = {}
        for p in positions:
            accounts_positions.setdefault(p.account_id, []).append(p)

        for account_id, acc_positions in accounts_positions.items():
            schemas = [PositionSchema.model_validate(p) for p in acc_positions]
            await self._position_repository.sync_by_account(account_id, schemas)

        return positions


async def position_api_factory(container: Container) -> PositionApi:
    return PositionApi(
        position_repository=await container.aget(PositionRepository),
    )
