from decimal import Decimal

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
    AccountHoldingRead,
    AccountHoldingsRead,
    AccountSchema,
    HoldingRead,
    PositionRead,
    PositionSchema,
)
from src.auth.api_types import UserId
from src.integration.api import IntegrationAccountApi, IntegrationUserApi
from src.market.api import MarketPricesApi, SecurityApi
from src.market.api_types import Security, SecurityId
from src.market.exception import SecurityNotFoundError
from src.market.schema import PriceSchema


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

    async def get_holdings_by_security(
        self, security_id: SecurityId, user_id: UserId
    ) -> list[AccountHoldingRead]:
        holdings = await self._position_repository.get_holdings_by_security(
            security_id, user_id
        )

        try:
            security = await self._security_service.get_by_id(security_id)
        except SecurityNotFoundError:
            return []

        latest_price_money = await self._market_prices.get_latest_close(security_id)
        latest_price = float(latest_price_money.amount) if latest_price_money else 0.0

        return [
            AccountHoldingRead(
                account_id=h.account_id,
                account_name=h.account_name,
                quantity=float(h.quantity),
                average_cost=h.average_cost,
                total_value=float(h.quantity) * latest_price,
                currency=str(security.currency),
            )
            for h in holdings
        ]

    async def get_account_holdings(self, account_id: AccountId) -> AccountHoldingsRead:
        account = await self._account_repository.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)

        positions = await self._position_repository.get_by_account(account_id)

        holdings, total_value, total_profit_loss = await self._calculate_holdings(
            account, positions
        )

        total_profit_loss_percent = None
        if account.net_deposits is not None:
            total_profit_loss = total_value - Money(
                account.net_deposits, account.currency
            )
            if account.net_deposits != 0:
                total_profit_loss_percent = (
                    float(total_profit_loss.amount) / float(account.net_deposits)
                ) * 100

        return AccountHoldingsRead(
            account_id=account.id,
            account_name=account.name,
            holdings=holdings,
            total_value=float(total_value.amount),
            total_profit_loss=float(total_profit_loss.amount),
            total_profit_loss_percent=total_profit_loss_percent,
            net_deposits=account.net_deposits,
            currency=str(account.currency),
        )

    async def _calculate_holdings(
        self, account: AccountSchema, positions: list[PositionSchema]
    ) -> tuple[list[HoldingRead], Money, Money]:
        holdings: list[HoldingRead] = []
        total_value = Money(0, account.currency)
        total_profit_loss = Money(0, account.currency)

        for position in positions:
            security = await self._security_service.get_by_id(position.security_id)
            if not security:
                continue

            latest_price = await self._market_prices.get_latest_price(security.id)
            current_price_money = (
                Money(latest_price.close, security.currency)
                if latest_price
                else Money(0, security.currency)
            )

            holding, value_money, pl_money = self._calculate_holding(
                account, position, security, current_price_money, latest_price
            )

            total_value += value_money
            total_profit_loss += pl_money
            holdings.append(holding)

        return holdings, total_value, total_profit_loss

    def _calculate_holding(
        self,
        account: AccountSchema,
        position: PositionSchema,
        security: Security,
        current_price_money: Money,
        latest_price_schema: PriceSchema | None = None,
    ) -> tuple[HoldingRead, Money, Money]:
        quantity = position.quantity
        avg_cost = position.average_cost or Decimal(0)
        # Use position's currency if available, fallback to security currency
        position_currency = position.currency or str(security.currency)

        # Base values in native stock currency
        unconverted_total_value = round(current_price_money * quantity, 2)
        unconverted_cost = Money(round(quantity * avg_cost, 2), position_currency)
        unconverted_pl = unconverted_total_value - unconverted_cost

        # Converted values in account currency
        value_money = self._currency_convert(
            unconverted_total_value,
            str(account.currency),
        )

        cost_money = self._currency_convert(
            unconverted_cost,
            str(account.currency),
        )

        pl_money = value_money - cost_money

        # Extra converted prices for UI
        converted_average_cost = self._currency_convert(
            Money(avg_cost, position_currency),
            str(account.currency),
        )
        converted_latest_price = self._currency_convert(
            current_price_money,
            str(account.currency),
        )

        holding = HoldingRead(
            id=position.id,
            security_id=security.id,
            security_symbol=security.symbol,
            security_name=security.name,
            quantity=float(quantity),
            average_cost=float(avg_cost),
            total_value=float(value_money.amount),
            profit_loss=float(pl_money.amount),
            currency=str(account.currency),
            security_currency=position_currency,
            unconverted_total_value=float(unconverted_total_value.amount),
            converted_average_cost=float(converted_average_cost.amount),
            converted_latest_price=float(converted_latest_price.amount),
            unconverted_profit_loss=float(unconverted_pl.amount),
            latest_price=float(latest_price_schema.close)
            if latest_price_schema
            else 0.0,
            price_date=latest_price_schema.date if latest_price_schema else None,
            updated_at=position.updated_at,
        )
        return holding, value_money, pl_money

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
            value=total_price,
        )

    def _compute_cost(self, position: PositionSchema, security: Security) -> Money:
        cost = round(position.quantity * (position.average_cost or 0), 2)

        return Money(cost, security.currency)

    async def _compute_price(
        self, position: PositionSchema, security: Security
    ) -> Money:
        security_price = await self._market_prices.get_latest_close(security.id)

        if security_price is None:
            return Money(0, security.currency)

        return round(security_price * position.quantity, 2)

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
