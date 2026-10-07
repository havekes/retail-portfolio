import logging
from decimal import Decimal
from typing import cast

from currency_converter import CurrencyConverter
from stockholm import Money
from stockholm.currency import BaseCurrency
from svcs import Container

from src.account.api_types import (
    Account,
    AccountId,
    AccountTotals,
    PositionId,
    ProfitLossBasis,
)
from src.account.exception import AccountNotFoundError, ApiSyncDisabledError
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
    UserHoldingRead,
)
from src.account.service.account import AccountService
from src.auth.api_types import UserId
from src.integration.api import IntegrationAccountApi, IntegrationUserApi
from src.market.api import MarketPricesApi, SecurityApi
from src.market.api_types import Security, SecurityId
from src.market.exception import SecurityNotFoundError
from src.market.fx import FxRateProvider
from src.market.schema import PriceSchema

logger = logging.getLogger(__name__)


class PositionService:
    _account_service: AccountService
    _fx_rates: CurrencyConverter
    _integration_account_api: IntegrationAccountApi
    _integration_user_api: IntegrationUserApi
    _market_prices: MarketPricesApi
    _position_repository: PositionRepository
    _security_service: SecurityApi

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        account_service: AccountService,
        fx_rates: CurrencyConverter,
        integration_account_api: IntegrationAccountApi,
        integration_user_api: IntegrationUserApi,
        market_prices: MarketPricesApi,
        position_repository: PositionRepository,
        security_service: SecurityApi,
    ):
        self._account_service = account_service
        self._fx_rates = fx_rates
        self._integration_account_api = integration_account_api
        self._integration_user_api = integration_user_api
        self._market_prices = market_prices
        self._position_repository = position_repository
        self._security_service = security_service

    async def sync_account_positions(
        self, user_id: UserId, account_id: AccountId
    ) -> None:
        """Sync positions for an account from the broker."""
        # Check that account exists
        account = await self._account_service.get_account(account_id)

        if not account.api_sync_enabled:
            raise ApiSyncDisabledError(account_id)

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
        self,
        security_id: SecurityId,
        user_id: UserId,
        offset: int = 0,
        limit: int = 50,
        display_currency: str | None = None,
    ) -> tuple[list[AccountHoldingRead], int]:
        """Get holdings for a specific security across all user accounts.

        ``total_value`` stays in the security's currency. ``display_total_value``
        converts it to ``display_currency`` (defaulting to each account's
        currency) so callers can aggregate rows without adding different
        currencies together.
        """
        holdings, total = await self._position_repository.get_holdings_by_security(
            security_id, user_id, offset, limit
        )

        # TODO propagate security not found error instead of returning
        # empty list which is ambiguous with "no holdings"
        try:
            security = await self._security_service.get_by_id(security_id)
        except SecurityNotFoundError:
            return [], 0

        latest_price_money = await self._market_prices.get_latest_close(security_id)
        latest_price = float(latest_price_money.amount) if latest_price_money else 0.0

        result_items: list[AccountHoldingRead] = []
        for h in holdings:
            holding_total_value = float(h.quantity) * latest_price
            account = await self._account_service.get_account(h.account_id)
            totals = await self.get_total_for_account(h.account_id, account.currency)
            account_total_value = float(totals.value.amount)

            target_currency = display_currency or str(account.currency)
            holding_money = Money(round(holding_total_value, 2), security.currency)
            converted_holding_money = self._currency_convert(
                holding_money, str(account.currency)
            )
            display_holding_money = self._currency_convert(
                holding_money, target_currency
            )

            account_percentage = None
            if account_total_value > 0:
                account_percentage = (
                    float(converted_holding_money.amount) / account_total_value
                ) * 100

            result_items.append(
                AccountHoldingRead(
                    account_id=h.account_id,
                    account_name=h.account_name,
                    quantity=float(h.quantity),
                    average_cost=h.average_cost,
                    total_value=holding_total_value,
                    currency=str(security.currency),
                    display_total_value=float(display_holding_money.amount),
                    display_currency=target_currency,
                    account_total_value=account_total_value,
                    account_percentage=account_percentage,
                )
            )

        return result_items, total

    async def get_user_holdings(
        self,
        user_id: UserId,
        offset: int = 0,
        limit: int = 50,
        display_currency: str = "CAD",
    ) -> tuple[list[UserHoldingRead], int]:
        """Get holdings across every account owned by the user.

        Native values stay in each account's currency; ``display_total_value``
        converts them to ``display_currency`` so callers can aggregate rows
        without adding different currencies together.
        """
        positions, total = await self._position_repository.get_by_user(
            user_id, offset, limit
        )

        positions_by_account: dict[AccountId, list[PositionSchema]] = {}
        for position in positions:
            positions_by_account.setdefault(position.account_id, []).append(position)

        result_items: list[UserHoldingRead] = []
        for account_id, account_positions in positions_by_account.items():
            account = await self._account_service.get_account(account_id)
            holdings, _, _, _ = await self._calculate_holdings(
                account, account_positions, display_currency
            )
            result_items.extend(
                UserHoldingRead(
                    **holding.model_dump(),
                    account_id=account.id,
                    account_name=account.name,
                )
                for holding in holdings
            )

        return result_items, total

    async def get_account_holdings(
        self, account_id: AccountId, offset: int = 0, limit: int = 50
    ) -> AccountHoldingsRead:
        """Get detailed holdings and totals for a specific account."""
        account = await self._account_service.get_account(account_id)

        # Calculate totals over all positions
        all_positions, _ = await self._position_repository.get_by_account(account_id)
        (
            _,
            positions_value,
            positions_cost,
            unpriced_positions,
        ) = await self._calculate_holdings(account, all_positions)
        totals = self._account_performance(
            account,
            positions_value,
            positions_cost,
            str(account.currency),
            unpriced_positions=unpriced_positions,
        )

        # Fetch paginated positions
        positions, total = await self._position_repository.get_by_account(
            account_id, offset=offset, limit=limit
        )

        holdings, _, _, _ = await self._calculate_holdings(account, positions)

        return AccountHoldingsRead(
            items=holdings,
            total=total,
            offset=offset,
            limit=limit,
            account_id=account.id,
            account_name=account.name,
            total_value=float(totals.value.amount),
            total_profit_loss=float(totals.profit_loss.amount),
            total_profit_loss_percent=totals.return_percent,
            profit_loss_basis=totals.basis,
            net_deposits=account.net_deposits,
            free_cash=account.free_cash,
            currency=str(account.currency),
            unpriced_positions=totals.unpriced_positions,
            pricing_incomplete=totals.pricing_incomplete,
        )

    async def get_total_for_account(
        self, account_id: AccountId, currency: BaseCurrency
    ) -> AccountTotals:
        """Calculate total cost and current value for an account in a currency."""
        account = await self._account_service.get_account(account_id)
        positions, _ = await self._position_repository.get_by_account(account_id)

        (
            _,
            positions_value,
            positions_cost,
            unpriced_positions,
        ) = await self._calculate_holdings(account, positions)

        if str(account.currency) != str(currency):
            positions_value = self._currency_convert(positions_value, str(currency))
            positions_cost = self._currency_convert(positions_cost, str(currency))

        return self._account_performance(
            account,
            positions_value,
            positions_cost,
            str(currency),
            unpriced_positions=unpriced_positions,
        )

    def _account_performance(
        self,
        account: AccountSchema,
        positions_value: Money,
        positions_cost: Money,
        currency: str,
        unpriced_positions: int = 0,
    ) -> AccountTotals:
        """Compute account totals and P/L against an explicit basis.

        Uses net deposits as the P/L basis when they are known, and falls back
        to the positions cost basis otherwise. ``cost`` (positions cost + cash)
        and ``value`` (positions value + cash) keep their previous meaning.

        ``unpriced_positions`` counts positions excluded from the totals because
        their security is missing or has no stored price; ``pricing_incomplete``
        reports that the totals understate the account.
        """
        cash = self._currency_convert(
            Money(account.free_cash, account.currency), currency
        )
        value = positions_value + cash
        cost = positions_cost + cash

        net_deposits: Money | None = None
        if account.net_deposits is not None:
            net_deposits = self._currency_convert(
                Money(account.net_deposits, account.currency), currency
            )

        if net_deposits is not None:
            basis: ProfitLossBasis = "net_deposits"
            profit_loss = value - net_deposits
            return_percent = (
                float(profit_loss.amount) / float(net_deposits.amount) * 100
                if net_deposits != 0
                else None
            )
        else:
            basis = "cost"
            profit_loss = positions_value - positions_cost
            return_percent = (
                float(profit_loss.amount) / float(positions_cost.amount) * 100
                if positions_cost != 0
                else None
            )

        return AccountTotals(
            cost=cost,
            value=value,
            cash=cash,
            net_deposits=net_deposits,
            profit_loss=profit_loss,
            return_percent=return_percent,
            basis=basis,
            unpriced_positions=unpriced_positions,
            pricing_incomplete=unpriced_positions > 0,
        )

    async def _calculate_holdings(
        self,
        account: AccountSchema,
        positions: list[PositionSchema],
        display_currency: str | None = None,
    ) -> tuple[list[HoldingRead], Money, Money, int]:
        """Calculate aggregated holdings, value, cost, and unpriced count.

        Returns totals in the account currency. Positions whose security is
        missing are skipped and counted. Positions without a stored price are
        still returned as rows (``total_value=0``, ``profit_loss=None``) but are
        excluded from value, cost and P/L, so a missing price cannot silently
        corrupt the account totals.

        ``display_currency`` defaults to the account currency, so account-scoped
        holdings report ``display_total_value == total_value``. The user-wide
        holdings call passes the user's preferred display currency instead.
        """
        target_currency = display_currency or str(account.currency)
        holdings: list[HoldingRead] = []
        total_value = Money(0, account.currency)
        total_cost = Money(0, account.currency)
        unpriced_positions = 0

        for position in positions:
            try:
                security = await self._security_service.get_by_id(position.security_id)
            except SecurityNotFoundError:
                logger.exception(
                    "Security not found for position %s with security_id %s",
                    position.id,
                    position.security_id,
                )
                unpriced_positions += 1
                continue

            latest_price = await self._market_prices.get_latest_price(security.id)
            if latest_price is None:
                logger.warning(
                    "No price for position %s with security_id %s; "
                    "excluding it from account totals",
                    position.id,
                    position.security_id,
                )
                unpriced_positions += 1
                holdings.append(
                    self._unpriced_holding(account, position, security, target_currency)
                )
                continue

            current_price_money = Money(latest_price.close, security.currency)
            holding, value_money, pl_money = self._calculate_holding(
                account,
                position,
                security,
                current_price_money,
                latest_price,
                target_currency,
            )

            total_value += value_money
            # cost = value - P/L (both already in the account currency)
            total_cost += value_money - pl_money
            holdings.append(holding)

        return holdings, total_value, total_cost, unpriced_positions

    def _unpriced_holding(
        self,
        account: AccountSchema,
        position: PositionSchema,
        security: Security,
        display_currency: str | None = None,
    ) -> HoldingRead:
        """Build a holding row for a position with no stored price.

        The row is surfaced to the user (``profit_loss=None``, ``total_value=0``)
        so the position is not silently dropped, while account totals exclude it.
        """
        quantity = position.quantity
        avg_cost = position.average_cost or Decimal(0)
        position_currency = position.currency or str(security.currency)
        converted_average_cost = self._currency_convert(
            Money(avg_cost, position_currency),
            str(account.currency),
        )
        target_currency = display_currency or str(account.currency)

        return HoldingRead(
            id=cast("PositionId", position.id),
            security_id=security.id,
            security_symbol=security.symbol,
            security_name=security.name,
            quantity=float(quantity),
            average_cost=float(avg_cost),
            total_value=0.0,
            profit_loss=None,
            currency=str(account.currency),
            display_total_value=0.0,
            display_currency=target_currency,
            security_currency=position_currency,
            unconverted_total_value=0.0,
            converted_average_cost=float(converted_average_cost.amount),
            converted_latest_price=None,
            unconverted_profit_loss=None,
            latest_price=None,
            price_date=None,
            updated_at=position.updated_at,
        )

    def _currency_convert(self, value: Money, to_currency: str) -> Money:
        """Convert a Money amount to the specified target currency."""
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

    def _calculate_holding(  # noqa: PLR0913, PLR0917
        self,
        account: AccountSchema,
        position: PositionSchema,
        security: Security,
        current_price_money: Money,
        latest_price_schema: PriceSchema | None = None,
        display_currency: str | None = None,
    ) -> tuple[HoldingRead, Money, Money]:
        """Calculate holding details, value, and profit/loss for a single position."""
        quantity = position.quantity
        avg_cost = position.average_cost or Decimal(0)
        # Use position's currency if available, fallback to security currency
        position_currency = position.currency or str(security.currency)

        # Base values in native stock currency
        unconverted_total_value = round(current_price_money * quantity, 2)
        unconverted_cost = Money(round(quantity * avg_cost, 2), position_currency)
        converted_unconverted_total_value = self._currency_convert(
            unconverted_total_value, position_currency
        )
        unconverted_pl = converted_unconverted_total_value - unconverted_cost

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

        # Display value for cross-currency aggregation (e.g. user-wide holdings)
        target_currency = display_currency or str(account.currency)
        display_value_money = self._currency_convert(value_money, target_currency)
        display_currency = target_currency

        holding = HoldingRead(
            id=cast("PositionId", position.id),
            security_id=security.id,
            security_symbol=security.symbol,
            security_name=security.name,
            quantity=float(quantity),
            average_cost=float(avg_cost),
            total_value=float(value_money.amount),
            profit_loss=float(pl_money.amount),
            currency=str(account.currency),
            display_total_value=float(display_value_money.amount),
            display_currency=display_currency,
            security_currency=position_currency,
            unconverted_total_value=float(converted_unconverted_total_value.amount),
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


async def position_service_factory(container: Container) -> PositionService:
    fx_provider: FxRateProvider = await container.aget(FxRateProvider)
    return PositionService(
        fx_rates=await fx_provider.converter(),
        market_prices=await container.aget(MarketPricesApi),
        position_repository=await container.aget(PositionRepository),
        security_service=await container.aget(SecurityApi),
        account_service=await container.aget(AccountService),
        integration_user_api=await container.aget(IntegrationUserApi),
        integration_account_api=await container.aget(IntegrationAccountApi),
    )
