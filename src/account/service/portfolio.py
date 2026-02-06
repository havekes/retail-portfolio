from fastapi import HTTPException, status
from svcs import Container

from src.account.api_types import PortfolioId
from src.account.exception import PortfolioNotFoundError
from src.account.repository import (
    AccountRepository,
    PortfolioRepository,
)
from src.account.schema import (
    PortfolioAccountUpdateRequest,
    PortfolioCreate,
    PortfolioRead,
)
from src.auth.api_types import UserId


class PortfolioService:
    _portfolio_repository: PortfolioRepository
    _account_repository: AccountRepository

    def __init__(
        self,
        portfolio_repository: PortfolioRepository,
        account_repository: AccountRepository,
    ):
        self._portfolio_repository = portfolio_repository
        self._account_repository = account_repository

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
        user_accounts = await self._account_repository.get_by_user(user_id)
        user_account_ids = {acc.id for acc in user_accounts}
        if not user_account_ids.issuperset(set(portfolio_create.accounts)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more accounts do not belong to the user",
            )

        return await self._portfolio_repository.create(user_id, portfolio_create)

    async def sync_portfolio_accounts(
        self,
        portfolio_id: PortfolioId,
        portfolio_account_update: PortfolioAccountUpdateRequest,
    ) -> PortfolioRead:
        portfolio = await self._portfolio_repository.get(portfolio_id)
        if not portfolio:
            raise PortfolioNotFoundError(portfolio_id)

        return await self._portfolio_repository.sync_accounts(
            portfolio_id, portfolio_account_update.accounts
        )

    async def delete_portfolio(self, portfolio_id: PortfolioId) -> None:
        portfolio = await self._portfolio_repository.get(portfolio_id)
        if not portfolio:
            raise PortfolioNotFoundError(portfolio_id)
        await self._portfolio_repository.delete(portfolio_id)


async def portfolio_service_factory(container: Container) -> PortfolioService:
    return PortfolioService(
        portfolio_repository=await container.aget(PortfolioRepository),
        account_repository=await container.aget(AccountRepository),
    )
