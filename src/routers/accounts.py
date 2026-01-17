from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from svcs.fastapi import DepContainer

from src.config.auth import current_user
from src.repositories.account import AccountRepository
from src.schemas import User
from src.schemas.account import Account, AccountRenameRequest
from src.services.authorization import AuthorizationService
from src.services.position import PositionService

router = APIRouter(prefix="/api/accounts")


@router.get("/")
async def accounts_list(
    services: DepContainer, user: Annotated[User, Depends(current_user)]
) -> list[Account]:
    """
    Get all accounts for the current user.
    """
    account_repository = await services.aget(AccountRepository)

    return await account_repository.get_by_user(user.id)


@router.patch("/{account_id}/rename")
async def account_rename(
    account_id: UUID,
    account_rename_request: AccountRenameRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
) -> Account:
    """
    Rename an existing account of the current user.
    """
    authorization_service = await services.aget(AuthorizationService)
    account_repository = await services.aget(AccountRepository)

    account = await account_repository.get(account_id)
    authorization_service.check_entity_owned_by_user(user, account)

    return await account_repository.rename(account_id, account_rename_request.name)


@router.get("/{account_id}/totals")
async def account_totals(
    account_id: UUID,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
):
    """
    Get accounts totals such as cost and price.
    """
    authorization_service = await services.aget(AuthorizationService)
    account_repository = await services.aget(AccountRepository)
    position_service = await services.aget(PositionService)

    account = await account_repository.get(account_id)
    authorization_service.check_entity_owned_by_user(user, account)

    return await position_service.get_total_for_account(account_id)
