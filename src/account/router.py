from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from svcs.fastapi import DepContainer

from src.account.api_types import AccountRenameRequest, AccountTotals
from src.account.repository import AccountRepository
from src.account.repository_sqlalchemy import sqlalchemy_account_repository_factory
from src.account.schema import AccountSchema
from src.config.auth import current_user
from src.schemas import User
from src.services.authorization import AuthorizationService
from src.services.position import PositionService

router = APIRouter(prefix="/api/account")


@router.get("/")
async def user_accounts(
    user: Annotated[User, Depends(current_user)],
    account_repository: Annotated[
        AccountRepository, sqlalchemy_account_repository_factory
    ],
) -> list[AccountSchema]:
    """
    Get all accounts for the current user.
    """

    return await account_repository.get_by_user(user.id)


@router.patch("/{account_id}/rename")
async def account_rename(
    account_id: UUID,
    account_rename_request: AccountRenameRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
    account_repository: Annotated[
        AccountRepository, sqlalchemy_account_repository_factory
    ],
) -> AccountSchema:
    """
    Rename an existing account of the current user.
    """
    authorization_service = await services.aget(AuthorizationService)

    account = await account_repository.get(account_id)
    authorization_service.check_entity_owned_by_user(user, account)

    return await account_repository.rename(account_id, account_rename_request.name)


@router.get("/{account_id}/totals")
async def account_totals(
    account_id: UUID,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
    account_repository: Annotated[
        AccountRepository, sqlalchemy_account_repository_factory
    ],
) -> AccountTotals:
    """
    Get accounts totals such as cost and price.
    """
    authorization_service = await services.aget(AuthorizationService)
    position_service = await services.aget(PositionService)

    account = await account_repository.get(account_id)
    authorization_service.check_entity_owned_by_user(user, account)

    return await position_service.get_total_for_account(account_id, currency="CAD")
