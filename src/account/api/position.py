from svcs import Container

from src.account.api_types import Position
from src.account.repository import PositionRepository


class PositionApi:
    _position_repository: PositionRepository

    def __init__(self, position_repository: PositionRepository) -> None:
        self._position_repository = position_repository

    def create(self, positions: list[Position]) -> list[Position]:
        return positions


async def position_api_factory(container: Container) -> PositionApi:
    return PositionApi(
        position_repository=await container.aget(PositionRepository),
    )
