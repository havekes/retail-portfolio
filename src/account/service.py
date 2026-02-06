from currency_converter import CurrencyConverter
from fastapi import HTTPException, status
from stockholm import Money
from stockholm.currency import BaseCurrency
from svcs.fastapi import DepContainer

from src.account.api_types import AccountId, AccountTotals, PortfolioId
from src.account.exception import PortfolioNotFoundException
from src.account.repository import (
    AccountRepository,
    PortfolioRepository,
    PositionRepository,
)
from src.account.repository_sqlalchemy import (
    sqlalchemy_account_repository_factory,
    sqlalchemy_portfolio_repository_factory,
    sqlalchemy_position_repository_factory,
)
from src.account.schema import (
    PortfolioAccountUpdate,
    PortfolioCreate,
    PortfolioRead,
    PositionRead,
    PositionSchema,
)
from src.auth.api_types import UserId
from src.market.api import MarketPricesApi, SecurityApi
from src.market.api_types import Security


class PositionService:
    _fx_rates: CurrencyConverter
    _market_prices: MarketPricesApi
    _position_repository: PositionRepository
    _security_service: SecurityApi

    def __init__(
        self,
        fx_rates: CurrencyConverter,
        market_prices: MarketPricesApi,
        position_repository: PositionRepository,
        security_service: SecurityApi,
    ):
        self._fx_rates = fx_rates
        self._market_prices = market_prices
        self._position_repository = position_repository
        self._security_service = security_service

    async def get_positions_by_account_with_security(
        self, account_id: AccountId
    ) -> list[PositionRead]:
        """Get positions for an account enriched with security data."""
        positions = await self._position_repository.get_by_account(account_id)

        result: list[PositionRead] = []
        for position in positions:
            security = await self._security_service.get_by_id(position.security_id)
            result.append(
                PositionRead(
                    id=position.id,
                    account_id=position.account_id,
                    security_id=position.security_id,
                    security_symbol=security.symbol if security else "UNKNOWN",
                    quantity=float(position.quantity),
                    average_cost=float(position.average_cost)
                    if position.average_cost
                    else None,
                    updated_at=position.updated_at,
                )
            )
        return result

    async def get_total_for_account(
        self, account_id: AccountId, currency: BaseCurrency
    ) -> AccountTotals:
        positions = await self._position_repository.get_by_account(account_id)

        total_cost = Money(0, currency)
        total_price = Money(0, currency)

        for position in positions:
            security = await self._security_service.get_by_id(position.security_id)
            unconverted_cost = self._compute_cost(position, security)
            unconverted_price = await self._compute_price(position, security)

            total_cost = total_cost + self._currency_convert(
                unconverted_cost, str(currency)
            )
            total_price = total_price + self._currency_convert(
                unconverted_price, str(currency)
            )

        return AccountTotals(
            cost=total_cost,
        )

    def _compute_cost(self, position: PositionSchema, security: Security) -> Money:
        cost = round(position.quantity * (position.average_cost or 0), 2)

        return Money(cost, security.currency)

    async def _compute_price(
        self, position: PositionSchema, security: Security
    ) -> Money:
        security_price = await self._market_prices.get_latest_close(security.id)

        return round(
            security_price or Money(0, security.currency) * position.quantity, 2
        )

    def _currency_convert(self, value: Money, to_currency: str) -> Money:
        if value.currency_code == to_currency:
            return value

        converted = round(
            self._fx_rates.convert(
                amount=value.amount,
                currency=value.currency_code,
                new_currency=to_currency,
            ),
            2,
        )

        return Money(converted, to_currency)


async def position_service_factory(container: DepContainer) -> PositionService:
    return PositionService(
        fx_rates=CurrencyConverter(),
        market_prices=await container.aget(MarketPricesApi),
        position_repository=await sqlalchemy_position_repository_factory(container),
        security_service=await container.aget(SecurityApi),
    )



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

    async def get_portfolio(
        self, portfolio_id: PortfolioId
    ) -> PortfolioRead:
        portfolio = await self._portfolio_repository.get(portfolio_id)
        if not portfolio:
            raise PortfolioNotFoundException(portfolio_id)
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
        portfolio_account_update: PortfolioAccountUpdate,
    ) -> PortfolioRead:
        portfolio = await self._portfolio_repository.get(portfolio_id)
        if not portfolio:
            raise PortfolioNotFoundException(portfolio_id)

        return await self._portfolio_repository.sync_accounts(
            portfolio_id, portfolio_account_update.accounts
        )

    async def delete_portfolio(
        self, portfolio_id: PortfolioId
    ) -> None:
        portfolio = await self._portfolio_repository.get(portfolio_id)
        if not portfolio:
            raise PortfolioNotFoundException(portfolio_id)
        await self._portfolio_repository.delete(portfolio_id)


async def portfolio_service_factory(container: DepContainer) -> PortfolioService:
    return PortfolioService(
        portfolio_repository=await sqlalchemy_portfolio_repository_factory(container),
        account_repository=await sqlalchemy_account_repository_factory(container),
    )
