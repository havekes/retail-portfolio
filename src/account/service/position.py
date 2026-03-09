from currency_converter import CurrencyConverter
from stockholm import Money
from stockholm.currency import BaseCurrency
from svcs import Container

from src.account.api_types import Account, AccountId, AccountTotals
from src.account.exception import AccountNotFoundError
from src.account.repository import (
    AccountRepository,
    PositionRepository,
)
from src.account.schema import (
    PositionRead,
    PositionSchema,
)
from src.auth.api_types import UserId
from src.integration.api import IntegrationAccountApi, IntegrationUserApi
from src.market.api import MarketPricesApi, SecurityApi
from src.market.api_types import Security


class PositionService:
    _fx_rates: CurrencyConverter
    _market_prices: MarketPricesApi
    _position_repository: PositionRepository
    _security_service: SecurityApi
    _account_repository: AccountRepository
    _integration_user_api: IntegrationUserApi
    _integration_account_api: IntegrationAccountApi

    def __init__(  # noqa: PLR0913
        self,
        fx_rates: CurrencyConverter,
        market_prices: MarketPricesApi,
        position_repository: PositionRepository,
        security_service: SecurityApi,
        account_repository: AccountRepository,
        integration_user_api: IntegrationUserApi,
        integration_account_api: IntegrationAccountApi,
    ):
        self._fx_rates = fx_rates
        self._market_prices = market_prices
        self._position_repository = position_repository
        self._security_service = security_service
        self._account_repository = account_repository
        self._integration_user_api = integration_user_api
        self._integration_account_api = integration_account_api

    async def sync_account_positions(
        self, user_id: UserId, account_id: AccountId
    ) -> None:
        # Check that account exists
        account = await self._account_repository.get(account_id)
        if account is None:
            raise AccountNotFoundError(account_id)

        if account.integration_user_id is None:
            # Nothing to do since the account was not imported from broker
            return

        # Check that the account's integration user exists
        await self._integration_user_api.get_by_id(account.integration_user_id)

        # Sync positions
        await self._integration_account_api.sync_account_positions(
            user_id=user_id,
            account=Account.model_validate(account),
            broker_account_id=account.external_id,
        )

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


async def position_service_factory(container: Container) -> PositionService:
    return PositionService(
        fx_rates=CurrencyConverter(),
        market_prices=await container.aget(MarketPricesApi),
        position_repository=await container.aget(PositionRepository),
        security_service=await container.aget(SecurityApi),
        account_repository=await container.aget(AccountRepository),
        integration_user_api=await container.aget(IntegrationUserApi),
        integration_account_api=await container.aget(IntegrationAccountApi),
    )
