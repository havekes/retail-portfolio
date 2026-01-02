from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from svcs.fastapi import DepContainer

from src.repositories.account import AccountRepository
from src.repositories.position import PositionRepository
from src.schemas.account import Account
from src.schemas.position import Position
from src.services.user import UserService

router = APIRouter(prefix="/api/positions")


@router.get("/{account_id}", response_model=list[Position])
async def positions_by_account(
    account_id: UUID,
    services: DepContainer,
) -> list[Position]:
    """
    Get all positions for the specified account.
    """
    user_service = await services.aget(UserService)
    account_repository = await services.aget(AccountRepository)
    position_repository = await services.aget(PositionRepository)

    current_user = await user_service.get_current_user()

    # Verify the account belongs to the current user
    account = await account_repository.get(account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(
            status_code=404, detail="Account not found or access denied"
        )

    return await position_repository.get_by_account(account_id)
