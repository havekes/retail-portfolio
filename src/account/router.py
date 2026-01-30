from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from svcs.fastapi import DepContainer

from src.account.api_types import AccountRenameRequest, AccountTotals
from src.account.repository import AccountRepository
from src.account.repository_sqlalchemy import sqlalchemy_account_repository_factory
from src.account.schema import AccountSchema
from src.account.service import PositionService, position_service_factory
from src.auth.api import AuthorizationApi
from src.auth.api_types import User
from src.config.auth import current_user

account_router = APIRouter(prefix="/api/account")


@account_router.get("/")
async def user_accounts(
    user: Annotated[User, Depends(current_user)],
    account_repository: Annotated[
        AccountRepository, Depends(sqlalchemy_account_repository_factory)
    ],
) -> list[AccountSchema]:
    """
    Get all accounts for the current user.
    """

    return await account_repository.get_by_user(user.id)


@account_router.patch("/{account_id}/rename")
async def account_rename(
    account_id: UUID,
    account_rename_request: AccountRenameRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
    account_repository: Annotated[
        AccountRepository, Depends(sqlalchemy_account_repository_factory)
    ],
) -> AccountSchema:
    """
    Rename an existing account of the current user.
    """
    authorization_api = await services.aget(AuthorizationApi)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    return await account_repository.rename(account_id, account_rename_request.name)


@account_router.get("/{account_id}/totals")
async def account_totals(
    account_id: UUID,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
    account_repository: Annotated[
        AccountRepository, Depends(sqlalchemy_account_repository_factory)
    ],
    position_service: Annotated[PositionService, Depends(position_service_factory)],
) -> AccountTotals:
    """
    Get accounts totals such as cost and price.
    """
    authorization_api = await services.aget(AuthorizationApi)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    if account is None:
        raise HTTPException(404)

    return await position_service.get_total_for_account(account_id, account.currency)
