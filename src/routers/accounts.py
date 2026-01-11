from uuid import UUID

from fastapi import APIRouter
from svcs.fastapi import DepContainer

from src.repositories.account import AccountRepository
from src.schemas.account import Account, AccountRenameRequest
from src.services.position import PositionService
from src.services.user import UserService

router = APIRouter(prefix="/api/accounts")


@router.get("/")
async def accounts_list(services: DepContainer) -> list[Account]:
    """
    Get all accounts for the current user.
    """
    user_service = await services.aget(UserService)
    account_repository = await services.aget(AccountRepository)

    current_user = await user_service.get_current_user()
    return await account_repository.get_by_user(current_user.id)


@router.patch("/{account_id}/rename")
async def account_rename(
    account_id: UUID,
    account_rename_request: AccountRenameRequest,
    services: DepContainer,
) -> Account:
    account_repository = await services.aget(AccountRepository)
    return await account_repository.rename(account_id, account_rename_request.name)


@router.get("/{account_id}/totals")
async def account_totals(account_id: UUID, services: DepContainer):
    position_service = await services.aget(PositionService)

    return await position_service.get_total_for_account(account_id)
