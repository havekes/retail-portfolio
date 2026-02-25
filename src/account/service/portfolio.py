from fastapi import HTTPException, status
from svcs import Container

from src.account.api_types import PortfolioId
from src.account.exception import PortfolioNotFoundError
from src.account.repository import (
    PortfolioRepository,
)
from src.account.schema import (
    PortfolioAccountUpdateRequest,
    PortfolioCreate,
    PortfolioRead,
)
from src.account.service.account import AccountService
from src.auth.api_types import UserId


class PortfolioService:
    _portfolio_repository: PortfolioRepository
    _account_service: AccountService

    def __init__(
        self,
        portfolio_repository: PortfolioRepository,
        account_service: AccountService,
    ):
        self._portfolio_repository = portfolio_repository
        self._account_service = account_service

    async def get_portfolio(self, portfolio_id: PortfolioId) -> PortfolioRead:
        portfolio = await self._portfolio_repository.get(portfolio_id)
        if not portfolio:
            raise PortfolioNotFoundError(portfolio_id)
        return portfolio

    async def get_portfolios_by_user(self, user_id: UserId) -> list[PortfolioRead]:
        return await self._portfolio_repository.get_by_user(user_id)

    async def create_portfolio(
        self, user_id: UserId, portfolio_create: PortfolioCreate
    ) -> PortfolioRead:
        # Validate that all account_ids belong to the user
        await self._account_service.check_accounts_belong_to_user(
            account_ids=portfolio_create.accounts, user_id=user_id
        )

        return await self._portfolio_repository.create(user_id, portfolio_create)

    async def sync_portfolio_accounts(
        self,
        user_id: UserId,
        portfolio_id: PortfolioId,
        portfolio_account_update: PortfolioAccountUpdateRequest,
    ) -> PortfolioRead:
        await self.get_portfolio(portfolio_id)

        # Validate that all account_ids belong to the user
        await self._account_service.check_accounts_belong_to_user(
            account_ids=portfolio_account_update.accounts, user_id=user_id
        )

        return await self._portfolio_repository.sync_accounts(
            portfolio_id, portfolio_account_update.accounts
        )

    async def delete_portfolio(self, portfolio_id: PortfolioId) -> None:
        await self.get_portfolio(portfolio_id)
        await self._portfolio_repository.delete(portfolio_id)


async def portfolio_service_factory(container: Container) -> PortfolioService:
    return PortfolioService(
        portfolio_repository=await container.aget(PortfolioRepository),
        account_service=await container.aget(AccountService),
    )
