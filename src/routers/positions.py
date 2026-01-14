from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from svcs.fastapi import DepContainer

from src.config.auth import current_user
from src.repositories.account import AccountRepository
from src.repositories.position import PositionRepository
from src.schemas import User
from src.schemas.position import Position
from src.services.authorization import AuthorizationService

router = APIRouter(prefix="/api/positions")


@router.get("/{account_id}", response_model=list[Position])
async def positions_by_account(
    account_id: UUID,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
) -> list[Position]:
    """
    Get all positions for the specified account.
    """
    authorization_service = await services.aget(AuthorizationService)
    account_repository = await services.aget(AccountRepository)
    position_repository = await services.aget(PositionRepository)

    account = await account_repository.get(account_id)
    authorization_service.check_entity_owned_by_user(user, account)

    return await position_repository.get_by_account(account_id)
