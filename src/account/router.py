from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from svcs.fastapi import DepContainer

from src.account.api_types import (
    AccountId,
    AccountRenameRequest,
    AccountTotals,
    PortfolioId,
)
from src.account.repository import AccountRepository
from src.account.repository_sqlalchemy import sqlalchemy_account_repository_factory
from src.account.schema import (
    AccountSchema,
    PortfolioAccountUpdate,
    PortfolioCreate,
    PortfolioRead,
    PositionRead,
)
from src.account.service import (
    PortfolioService,
    PositionService,
    portfolio_service_factory,
    position_service_factory,
)
from src.auth.api import AuthorizationApi, current_user
from src.auth.api_types import User

account_router = APIRouter(prefix="/api/accounts")
portfolio_router = APIRouter(prefix="/api/portfolios")


@portfolio_router.get("/")
async def portfolios_list(
    user: Annotated[User, Depends(current_user)],
    portfolio_service: Annotated[PortfolioService, Depends(portfolio_service_factory)],
) -> list[PortfolioRead]:
    """
    Get all portfolios for the current user.
    """
    return await portfolio_service.get_portfolios_by_user(user.id)


@portfolio_router.post("/")
async def portfolio_create(
    portfolio_create_request: PortfolioCreate,
    user: Annotated[User, Depends(current_user)],
    portfolio_service: Annotated[PortfolioService, Depends(portfolio_service_factory)],
) -> PortfolioRead:
    """
    Create a new portfolio for the current user.
    """
    return await portfolio_service.create_portfolio(user.id, portfolio_create_request)


@portfolio_router.put("/{portfolio_id}/accounts")
async def portfolio_accounts_update(
    portfolio_id: PortfolioId,
    portfolio_account_update_request: PortfolioAccountUpdate,
    user: Annotated[User, Depends(current_user)],
    portfolio_service: Annotated[PortfolioService, Depends(portfolio_service_factory)],
    account_repository: Annotated[AccountRepository, Depends(sqlalchemy_account_repository_factory)],
    services: DepContainer,
) -> PortfolioRead:
    """
    Update the list of accounts associated with a portfolio.
    """
    authorization_api = await services.aget(AuthorizationApi)

    # Validate that all account_ids belong to the user
    user_accounts = await account_repository.get_by_user(user.id)
    user_account_ids = {account.id for account in user_accounts}
    if not user_account_ids.issuperset(set(portfolio_account_update_request.accounts)):
        raise HTTPException(
            status_code=400,
            detail="One or more accounts do not belong to the user",
        )

    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    authorization_api.check_entity_owned_by_user(user, portfolio)

    return await portfolio_service.sync_portfolio_accounts(
        portfolio_id, portfolio_account_update_request
    )


@portfolio_router.delete("/{portfolio_id}")
async def portfolio_delete(
    portfolio_id: PortfolioId,
    user: Annotated[User, Depends(current_user)],
    portfolio_service: Annotated[PortfolioService, Depends(portfolio_service_factory)],
    services: DepContainer,
) -> Response:
    """
    Delete a portfolio.
    """
    authorization_api = await services.aget(AuthorizationApi)

    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    authorization_api.check_entity_owned_by_user(user, portfolio)

    await portfolio_service.delete_portfolio(portfolio_id)

    return Response(status_code=204)


@account_router.get("/")
async def accounts_list(
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
    account_id: AccountId,
    account_rename_request: AccountRenameRequest,
    user: Annotated[User, Depends(current_user)],
    account_repository: Annotated[
        AccountRepository, Depends(sqlalchemy_account_repository_factory)
    ],
    services: DepContainer,
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
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    account_repository: Annotated[
        AccountRepository, Depends(sqlalchemy_account_repository_factory)
    ],
    position_service: Annotated[PositionService, Depends(position_service_factory)],
    services: DepContainer,
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


@account_router.get("/{account_id}/positions")
async def positions_by_account(
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    account_repository: Annotated[
        AccountRepository, Depends(sqlalchemy_account_repository_factory)
    ],
    position_service: Annotated[PositionService, Depends(position_service_factory)],
    services: DepContainer,
) -> list[PositionRead]:
    """Get all positions for a specific account owned by the current user."""
    authorization_api = await services.aget(AuthorizationApi)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    return await position_service.get_positions_by_account_with_security(account_id)
