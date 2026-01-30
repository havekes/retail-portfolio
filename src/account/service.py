from uuid import UUID

from currency_converter import CurrencyConverter
from stockholm import Money
from svcs import Container

from src.account.api_types import AccountTotals
from src.account.repository import PositionRepository
from src.account.repository_sqlalchemy import sqlalchemy_position_repository_factory
from src.account.schema import PositionSchema
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

    async def get_total_for_account(
        self, account_id: UUID, currency: str
    ) -> AccountTotals:
        positions = await self._position_repository.get_by_account(account_id)

        total_cost = Money(0, currency)
        total_price = Money(0, currency)

        for position in positions:
            security = await self._security_service.get_by_id(position.security_id)
            unconverted_cost = self._compute_cost(position, security)
            unconverted_price = await self._compute_price(position, security)

            total_cost = total_cost + self._currency_convert(unconverted_cost, currency)
            total_price = total_price + self._currency_convert(
                unconverted_price, currency
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
            self._fx_rates.convert(  # pyright: ignore[reportUnknownArgumentType]
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
        position_repository=await sqlalchemy_position_repository_factory(container),
        security_service=await container.aget(SecurityApi),
    )
