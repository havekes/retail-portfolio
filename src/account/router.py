from typing import Annotated
from uuid import UUID

import redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from svcs.fastapi import DepContainer

from src.account.api_types import (
    AccountId,
    AccountRenameRequest,
    AccountTotals,
    PortfolioId,
    UserPreferences,
)
from src.account.exception import AccountNotFoundError
from src.account.repository import AccountRepository
from src.account.schema import (
    AccountHoldingRead,
    AccountHoldingsRead,
    AccountSchema,
    PortfolioAccountUpdateRequest,
    PortfolioCreate,
    PortfolioRead,
)
from src.account.service.account import AccountService
from src.account.service.portfolio import PortfolioService
from src.account.service.position import PositionService
from src.auth.api import AuthorizationApi, UserApi, current_user
from src.auth.api_types import User
from src.config.limiter import limiter
from src.core.pagination import PaginatedResponse, PaginationParams
from src.integration.sync_status import get_active_syncs

account_router = APIRouter(prefix="/accounts")
portfolio_router = APIRouter(prefix="/portfolios")


@portfolio_router.get("/")
async def portfolios(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> list[PortfolioRead]:
    """
    Get all portfolios for the current user.
    """
    portfolio_service = await services.aget(PortfolioService)
    return await portfolio_service.get_portfolios_by_user(user.id)


@portfolio_router.post("/")
async def portfolio_create(
    portfolio_create_request: PortfolioCreate,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> PortfolioRead:
    """
    Create a new portfolio for the current user.
    """
    portfolio_service = await services.aget(PortfolioService)
    return await portfolio_service.create_portfolio(user.id, portfolio_create_request)


@portfolio_router.put("/{portfolio_id}/accounts")
async def portfolio_accounts_sync(
    portfolio_id: PortfolioId,
    portfolio_account_update_request: PortfolioAccountUpdateRequest,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> PortfolioRead:
    """
    Sync the list of accounts associated with a portfolio.
    """
    authorization_api = await services.aget(AuthorizationApi)
    portfolio_service = await services.aget(PortfolioService)
    account_service = await services.aget(AccountService)

    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    authorization_api.check_entity_owned_by_user(user, portfolio)

    await account_service.check_accounts_belong_to_user(
        account_ids=portfolio_account_update_request.accounts,
        user_id=user.id,
    )

    return await portfolio_service.sync_portfolio_accounts(
        user_id=user.id,
        portfolio_id=portfolio_id,
        portfolio_account_update=portfolio_account_update_request,
    )


@portfolio_router.delete("/{portfolio_id}")
async def portfolio_delete(
    portfolio_id: PortfolioId,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> Response:
    """
    Delete a portfolio.
    """
    authorization_api = await services.aget(AuthorizationApi)
    portfolio_service = await services.aget(PortfolioService)

    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    authorization_api.check_entity_owned_by_user(user, portfolio)

    await portfolio_service.delete_portfolio(portfolio_id)

    return Response(status_code=204)


@account_router.get("/")
async def accounts(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> list[AccountSchema]:
    """
    Get all accounts for the current user.
    """
    account_repository = await services.aget(AccountRepository)
    return await account_repository.get_by_user(user.id)


@account_router.get("/sync-status")
async def account_sync_status(
    user: Annotated[User, Depends(current_user)],
) -> dict[str, list[str]]:
    """Return the IDs of accounts that currently have an active sync job."""
    try:
        active_ids = await get_active_syncs(user.id)
        return {"account_ids": [str(aid) for aid in active_ids]}
    except redis.RedisError as e:
        raise HTTPException(
            status_code=503,
            detail="Sync status service unavailable",
        ) from e


@account_router.get("/me/preferences")
async def get_preferences(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> dict:
    """Return the current user's chart preferences."""
    user_api = await services.aget(UserApi)
    prefs = await user_api.get_preferences(user.id)
    return prefs if prefs is not None else {}


@account_router.put("/me/preferences")
async def put_preferences(
    payload: UserPreferences,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> dict:
    """Store the current user's chart preferences."""
    user_api = await services.aget(UserApi)
    # exclude_none=True: explicit null fields are dropped; server does not store them
    await user_api.save_preferences(user.id, payload.model_dump(exclude_none=True))
    return await user_api.get_preferences(user.id) or {}


@account_router.patch("/me/preferences")
async def patch_preferences(
    payload: UserPreferences,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> dict:
    """Partially update the current user's preferences."""
    user_api = await services.aget(UserApi)
    # exclude_none=True: explicit null fields are dropped;
    # server only updates provided fields
    return await user_api.patch_preferences(
        user.id, payload.model_dump(exclude_none=True)
    )


@account_router.patch("/{account_id}/rename")
async def account_rename(
    account_id: AccountId,
    account_rename_request: AccountRenameRequest,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> AccountSchema:
    """
    Rename an existing account of the current user.
    """
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    return await account_repository.rename(account_id, account_rename_request.name)


@account_router.delete("/{account_id}")
async def account_delete(
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> Response:
    """
    Delete an account.
    """
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)
    account_service = await services.aget(AccountService)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    await account_service.delete_account(account_id)

    return Response(status_code=204)


@account_router.get("/{account_id}/totals")
async def account_totals(
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> AccountTotals:
    """
    Get accounts totals such as cost and price.
    """
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)
    position_service = await services.aget(PositionService)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    if account is None:
        raise HTTPException(404)

    return await position_service.get_total_for_account(account_id, account.currency)


@account_router.get("/holdings/{security_id}")
async def security_holdings(
    security_id: UUID,
    user: Annotated[User, Depends(current_user)],
    pagination: Annotated[PaginationParams, Depends()],
    services: DepContainer,
) -> PaginatedResponse[AccountHoldingRead]:
    """Get all holdings for a specific security across user accounts."""
    position_service = await services.aget(PositionService)
    holdings, total = await position_service.get_holdings_by_security(
        security_id, user.id, offset=pagination.offset, limit=pagination.limit
    )
    return PaginatedResponse(
        items=holdings, total=total, offset=pagination.offset, limit=pagination.limit
    )


@account_router.get("/{account_id}/holdings")
async def account_holdings(
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    pagination: Annotated[PaginationParams, Depends()],
    services: DepContainer,
) -> AccountHoldingsRead:
    """Get detailed holdings for a specific account."""
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)
    position_service = await services.aget(PositionService)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    return await position_service.get_account_holdings(
        account_id, offset=pagination.offset, limit=pagination.limit
    )


@account_router.post("/{account_id}/sync")
@limiter.limit("3/minute")
async def account_sync_positions(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> dict:
    """
    Enqueue a background task to sync positions for the given account.
    """
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)
    position_service = await services.aget(PositionService)

    account = await account_repository.get(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    authorization_api.check_entity_owned_by_user(user, account)

    try:
        await position_service.sync_account_positions(user.id, account_id)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return {"accepted": True}
