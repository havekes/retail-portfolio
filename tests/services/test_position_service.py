"""Unit tests for the user-wide holdings calculation in PositionService."""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from currency_converter import CurrencyConverter
from stockholm import Currency, Money

from src.account.api_types import AccountId
from src.account.repository import PositionRepository
from src.account.schema import AccountSchema, PositionSchema, UserHoldingRead
from src.account.service.account import AccountService
from src.account.service.position import PositionService
from src.core.enum import AccountTypeEnum, InstitutionEnum
from src.market.api import MarketPricesApi, SecurityApi
from src.market.api_types import Security
from src.market.exception import SecurityNotFoundError
from src.market.schema import PriceSchema


def _account(account_id: AccountId, name: str) -> AccountSchema:
    return AccountSchema(
        id=account_id,
        external_id=str(account_id),
        name=name,
        user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        currency=Currency("USD"),
    )


def _position(
    position_id: int, account_id: AccountId, security_id, quantity: str
) -> PositionSchema:
    return PositionSchema(
        id=position_id,
        account_id=account_id,
        security_id=security_id,
        quantity=Decimal(quantity),
        average_cost=Decimal("10.0"),
    )


def _security(security_id, symbol: str = "AAPL") -> Security:
    return Security(
        id=security_id,
        symbol=symbol,
        exchange="NASDAQ",
        currency=Currency("USD"),
        name="Apple Inc.",
        isin=None,
        is_active=True,
        updated_at=datetime.now(UTC),
    )


def _price(security_id, close: str = "100.0") -> PriceSchema:
    return PriceSchema(
        security_id=security_id,
        date=date(2026, 1, 2),
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        adjusted_close=Decimal(close),
        volume=1000,
    )


def _build_service(
    positions: list[PositionSchema],
    total: int,
    accounts: dict[AccountId, AccountSchema],
    security: Security,
) -> tuple[PositionService, AsyncMock, AsyncMock]:
    position_repository = AsyncMock(spec=PositionRepository)
    position_repository.get_by_user = AsyncMock(return_value=(positions, total))

    account_service = AsyncMock(spec=AccountService)
    account_service.get_account = AsyncMock(
        side_effect=lambda account_id: accounts[account_id]
    )

    security_service = AsyncMock(spec=SecurityApi)
    security_service.get_by_id = AsyncMock(return_value=security)

    market_prices = AsyncMock(spec=MarketPricesApi)
    market_prices.get_latest_price = AsyncMock(return_value=_price(security.id))

    service = PositionService(
        account_service=account_service,
        fx_rates=CurrencyConverter(),
        integration_account_api=AsyncMock(),
        integration_user_api=AsyncMock(),
        market_prices=market_prices,
        position_repository=position_repository,
        security_service=security_service,
    )
    return service, account_service, position_repository


def _build_account_totals_service(
    account: AccountSchema,
    positions: list[PositionSchema],
    security: Security,
    close: str,
) -> PositionService:
    """Build a PositionService wired to a single account and market price.

    Both totals paths are stubbed: ``get_total_for_account`` reads
    ``get_latest_close`` while ``get_account_holdings`` reads
    ``get_latest_price``.
    """
    position_repository = AsyncMock(spec=PositionRepository)
    position_repository.get_by_account = AsyncMock(
        return_value=(positions, len(positions))
    )

    account_service = AsyncMock(spec=AccountService)
    account_service.get_account = AsyncMock(return_value=account)

    security_service = AsyncMock(spec=SecurityApi)
    security_service.get_by_id = AsyncMock(return_value=security)

    market_prices = AsyncMock(spec=MarketPricesApi)
    market_prices.get_latest_close = AsyncMock(
        return_value=Money(Decimal(close), security.currency)
    )
    market_prices.get_latest_price = AsyncMock(return_value=_price(security.id, close))

    return PositionService(
        account_service=account_service,
        fx_rates=CurrencyConverter(),
        integration_account_api=AsyncMock(),
        integration_user_api=AsyncMock(),
        market_prices=market_prices,
        position_repository=position_repository,
        security_service=security_service,
    )


@pytest.mark.anyio
async def test_get_user_holdings_groups_by_account_and_stamps_context():
    """Positions are grouped per account and stamped with account context."""
    user_id = uuid4()
    account_a = _account(uuid4(), "Account A")
    account_b = _account(uuid4(), "Account B")
    security = _security(uuid4())
    positions = [
        _position(1, account_a.id, security.id, "10"),
        _position(2, account_a.id, security.id, "5"),
        _position(3, account_b.id, security.id, "2"),
    ]
    service, account_service, position_repository = _build_service(
        positions,
        total=3,
        accounts={account_a.id: account_a, account_b.id: account_b},
        security=security,
    )

    items, total = await service.get_user_holdings(user_id, offset=0, limit=50)

    assert total == 3
    assert len(items) == 3
    assert all(isinstance(item, UserHoldingRead) for item in items)
    assert {item.account_id: item.account_name for item in items} == {
        account_a.id: "Account A",
        account_b.id: "Account B",
    }
    assert sorted(item.quantity for item in items) == [2.0, 5.0, 10.0]
    assert all(item.security_symbol == "AAPL" for item in items)

    position_repository.get_by_user.assert_awaited_once_with(user_id, 0, 50)
    # Account context is resolved once per account, not once per position.
    assert account_service.get_account.await_count == 2


@pytest.mark.anyio
async def test_get_total_for_account_includes_free_cash():
    """Verify get_total_for_account adds account free_cash to totals.value and totals.cost."""
    account_id = uuid4()
    account = _account(account_id, "Test Account")
    account.free_cash = 250.0

    security = _security(uuid4())
    position = _position(1, account_id, security.id, "10")

    position_repository = AsyncMock(spec=PositionRepository)
    position_repository.get_by_account = AsyncMock(return_value=([position], 1))

    account_service = AsyncMock(spec=AccountService)
    account_service.get_account = AsyncMock(return_value=account)

    security_service = AsyncMock(spec=SecurityApi)
    security_service.get_by_id = AsyncMock(return_value=security)

    market_prices = AsyncMock(spec=MarketPricesApi)
    market_prices.get_latest_price = AsyncMock(return_value=_price(security.id))

    service = PositionService(
        account_service=account_service,
        fx_rates=CurrencyConverter(),
        integration_account_api=AsyncMock(),
        integration_user_api=AsyncMock(),
        market_prices=market_prices,
        position_repository=position_repository,
        security_service=security_service,
    )

    totals = await service.get_total_for_account(account_id, Currency("USD"))

    # cost: 10 * $10 (avg_cost) + $250 (free cash) = $350
    assert float(totals.cost.amount) == 350.0
    # value: 10 * $100 (market close) + $250 (free cash) = $1250
    assert float(totals.value.amount) == 1250.0


@pytest.mark.anyio
async def test_get_account_holdings_includes_free_cash():
    """Verify get_account_holdings adds free_cash to total_value and reflects in P/L."""
    account_id = uuid4()
    account = _account(account_id, "Test Account")
    account.free_cash = 500.0
    account.net_deposits = 1000.0

    security = _security(uuid4())
    position = _position(1, account_id, security.id, "10")

    position_repository = AsyncMock(spec=PositionRepository)
    position_repository.get_by_account = AsyncMock(return_value=([position], 1))

    account_service = AsyncMock(spec=AccountService)
    account_service.get_account = AsyncMock(return_value=account)

    security_service = AsyncMock(spec=SecurityApi)
    security_service.get_by_id = AsyncMock(return_value=security)

    market_prices = AsyncMock(spec=MarketPricesApi)
    market_prices.get_latest_price = AsyncMock(return_value=_price(security.id))

    service = PositionService(
        account_service=account_service,
        fx_rates=CurrencyConverter(),
        integration_account_api=AsyncMock(),
        integration_user_api=AsyncMock(),
        market_prices=market_prices,
        position_repository=position_repository,
        security_service=security_service,
    )

    holdings_read = await service.get_account_holdings(account_id, offset=0, limit=50)

    # 10 * 100 (price) + 500 (free cash) = 1500
    assert holdings_read.total_value == 1500.0
    # 1500 (value) - 1000 (net deposits) = 500
    assert holdings_read.total_profit_loss == 500.0
    # 500 / 1000 * 100 = 50.0%
    assert holdings_read.total_profit_loss_percent == 50.0
    assert holdings_read.free_cash == 500.0


@pytest.mark.anyio
async def test_get_account_holdings_currency_mismatch_position_cad_security_usd():
    """Verify get_account_holdings computes without CurrencyMismatchError when position.currency == 'CAD' and security.currency == 'USD'."""
    account_id = uuid4()
    account = _account(account_id, "Test Account")
    account.currency = Currency("CAD")

    security = _security(uuid4())
    security.currency = Currency("USD")

    position = _position(1, account_id, security.id, "10")
    position.currency = "CAD"
    position.average_cost = Decimal("12.0")

    position_repository = AsyncMock(spec=PositionRepository)
    position_repository.get_by_account = AsyncMock(return_value=([position], 1))

    account_service = AsyncMock(spec=AccountService)
    account_service.get_account = AsyncMock(return_value=account)

    security_service = AsyncMock(spec=SecurityApi)
    security_service.get_by_id = AsyncMock(return_value=security)

    market_prices = AsyncMock(spec=MarketPricesApi)
    market_prices.get_latest_price = AsyncMock(return_value=_price(security.id))

    service = PositionService(
        account_service=account_service,
        fx_rates=CurrencyConverter(),
        integration_account_api=AsyncMock(),
        integration_user_api=AsyncMock(),
        market_prices=market_prices,
        position_repository=position_repository,
        security_service=security_service,
    )

    holdings_read = await service.get_account_holdings(account_id, offset=0, limit=50)

    assert len(holdings_read.items) == 1
    holding = holdings_read.items[0]
    assert holding.security_currency == "CAD"
    assert holding.unconverted_total_value > 0
    assert holding.unconverted_profit_loss is not None


@pytest.mark.anyio
async def test_get_total_for_account_uses_net_deposits_basis():
    """net_deposits known: P/L is present value minus net deposits."""
    account = _account(uuid4(), "Net Deposits Account")
    account.free_cash = 50.0
    account.net_deposits = 1000.0

    security = _security(uuid4())
    # 10 shares @ market 110 => positions value 1100; cost 10 * 10 = 100.
    position = _position(1, account.id, security.id, "10")
    service = _build_account_totals_service(account, [position], security, "110.0")

    totals = await service.get_total_for_account(account.id, Currency("USD"))

    assert float(totals.value.amount) == 1150.0
    assert float(totals.cost.amount) == 150.0
    assert float(totals.cash.amount) == 50.0
    assert totals.net_deposits is not None
    assert float(totals.net_deposits.amount) == 1000.0
    assert float(totals.profit_loss.amount) == 150.0
    assert totals.return_percent == 15.0
    assert totals.basis == "net_deposits"


@pytest.mark.anyio
async def test_get_account_holdings_uses_net_deposits_basis():
    """Holdings totals agree with get_total_for_account's net-deposits basis."""
    account = _account(uuid4(), "Net Deposits Account")
    account.free_cash = 50.0
    account.net_deposits = 1000.0

    security = _security(uuid4())
    position = _position(1, account.id, security.id, "10")
    service = _build_account_totals_service(account, [position], security, "110.0")

    holdings = await service.get_account_holdings(account.id)

    assert holdings.total_value == 1150.0
    assert holdings.total_profit_loss == 150.0
    assert holdings.total_profit_loss_percent == 15.0
    assert holdings.profit_loss_basis == "net_deposits"


@pytest.mark.anyio
async def test_get_total_for_account_cost_basis_excludes_cash_from_denominator():
    """net_deposits unknown: P/L is positions value minus positions cost."""
    account = _account(uuid4(), "Cost Basis Account")
    account.free_cash = 500.0
    account.net_deposits = None

    security = _security(uuid4())
    position = _position(1, account.id, security.id, "10")
    position.average_cost = Decimal("100.0")  # positions cost 1000

    service = _build_account_totals_service(account, [position], security, "110.0")

    totals = await service.get_total_for_account(account.id, Currency("USD"))

    assert float(totals.value.amount) == 1600.0
    assert float(totals.cost.amount) == 1500.0
    assert float(totals.cash.amount) == 500.0
    assert totals.net_deposits is None
    assert float(totals.profit_loss.amount) == 100.0
    assert totals.return_percent == 10.0
    assert totals.basis == "cost"


@pytest.mark.anyio
async def test_zero_net_deposits_uses_net_deposits_basis_with_null_return():
    """A zero net-deposits basis keeps the basis but cannot produce a percent."""
    account = _account(uuid4(), "Zero Net Deposits Account")
    account.free_cash = 50.0
    account.net_deposits = 0.0

    security = _security(uuid4())
    position = _position(1, account.id, security.id, "10")
    service = _build_account_totals_service(account, [position], security, "110.0")

    totals = await service.get_total_for_account(account.id, Currency("USD"))

    assert totals.basis == "net_deposits"
    assert float(totals.profit_loss.amount) == 1150.0
    assert totals.return_percent is None

    holdings = await service.get_account_holdings(account.id)
    assert holdings.profit_loss_basis == "net_deposits"
    assert holdings.total_profit_loss == 1150.0
    assert holdings.total_profit_loss_percent is None


@pytest.mark.anyio
async def test_total_and_holdings_agree_on_performance():
    """The two totals paths return the same performance for one account."""
    account = _account(uuid4(), "Agreement Account")
    account.free_cash = 50.0
    account.net_deposits = 1000.0

    security = _security(uuid4())
    position = _position(1, account.id, security.id, "10")
    service = _build_account_totals_service(account, [position], security, "110.0")

    totals = await service.get_total_for_account(account.id, Currency("USD"))
    holdings = await service.get_account_holdings(account.id)

    assert float(totals.value.amount) == holdings.total_value
    assert float(totals.profit_loss.amount) == holdings.total_profit_loss
    assert totals.return_percent == holdings.total_profit_loss_percent
    assert totals.basis == holdings.profit_loss_basis


def _build_multi_security_service(
    account: AccountSchema,
    positions: list[PositionSchema],
    securities: dict,
    prices: dict,
) -> PositionService:
    """Wire a PositionService with per-security prices (None means unpriced)."""
    position_repository = AsyncMock(spec=PositionRepository)
    position_repository.get_by_account = AsyncMock(
        return_value=(positions, len(positions))
    )

    account_service = AsyncMock(spec=AccountService)
    account_service.get_account = AsyncMock(return_value=account)

    security_service = AsyncMock(spec=SecurityApi)
    security_service.get_by_id = AsyncMock(
        side_effect=lambda security_id: securities[security_id]
    )

    market_prices = AsyncMock(spec=MarketPricesApi)
    market_prices.get_latest_price = AsyncMock(
        side_effect=lambda security_id: (
            _price(security_id, prices[security_id])
            if prices.get(security_id) is not None
            else None
        )
    )

    return PositionService(
        account_service=account_service,
        fx_rates=CurrencyConverter(),
        integration_account_api=AsyncMock(),
        integration_user_api=AsyncMock(),
        market_prices=market_prices,
        position_repository=position_repository,
        security_service=security_service,
    )


@pytest.mark.anyio
async def test_unpriced_position_is_excluded_from_totals_and_counted():
    """A position with no stored price is reported, not silently valued at zero."""
    account = _account(uuid4(), "Partially Priced")
    account.free_cash = 0.0
    account.net_deposits = None

    priced_security = _security(uuid4(), "AAA")
    unpriced_security = _security(uuid4(), "BBB")

    priced = _position(1, account.id, priced_security.id, "10")
    priced.average_cost = Decimal("100.0")  # cost 1000, priced value 1100
    unpriced = _position(2, account.id, unpriced_security.id, "5")
    unpriced.average_cost = Decimal("100.0")  # cost 500, no price

    service = _build_multi_security_service(
        account,
        [priced, unpriced],
        {priced_security.id: priced_security, unpriced_security.id: unpriced_security},
        {priced_security.id: "110.0", unpriced_security.id: None},
    )

    totals = await service.get_total_for_account(account.id, Currency("USD"))

    # Only the priced position contributes: value 1100, cost 1000, P/L 100.
    assert float(totals.value.amount) == 1100.0
    assert float(totals.cost.amount) == 1000.0
    assert float(totals.profit_loss.amount) == 100.0
    assert totals.basis == "cost"
    assert totals.unpriced_positions == 1
    assert totals.pricing_incomplete is True

    holdings = await service.get_account_holdings(account.id)

    assert holdings.total_value == 1100.0
    assert holdings.total_profit_loss == 100.0
    assert holdings.unpriced_positions == 1
    assert holdings.pricing_incomplete is True

    unpriced_row = next(h for h in holdings.items if h.id == 2)
    assert unpriced_row.profit_loss is None
    assert unpriced_row.total_value == 0.0


@pytest.mark.anyio
async def test_missing_security_is_skipped_logged_and_counted(caplog):
    """SecurityNotFoundError is caught per position instead of failing the request."""
    account = _account(uuid4(), "Orphaned Position")
    account.free_cash = 0.0
    account.net_deposits = None

    security = _security(uuid4())
    position = _position(1, account.id, security.id, "10")

    position_repository = AsyncMock(spec=PositionRepository)
    position_repository.get_by_account = AsyncMock(return_value=([position], 1))

    account_service = AsyncMock(spec=AccountService)
    account_service.get_account = AsyncMock(return_value=account)

    security_service = AsyncMock(spec=SecurityApi)
    security_service.get_by_id = AsyncMock(
        side_effect=SecurityNotFoundError(security.id)
    )

    market_prices = AsyncMock(spec=MarketPricesApi)
    market_prices.get_latest_price = AsyncMock(return_value=None)

    service = PositionService(
        account_service=account_service,
        fx_rates=CurrencyConverter(),
        integration_account_api=AsyncMock(),
        integration_user_api=AsyncMock(),
        market_prices=market_prices,
        position_repository=position_repository,
        security_service=security_service,
    )

    with caplog.at_level(logging.ERROR):
        totals = await service.get_total_for_account(account.id, Currency("USD"))
        holdings = await service.get_account_holdings(account.id)

    assert totals.unpriced_positions == 1
    assert totals.pricing_incomplete is True
    assert float(totals.value.amount) == 0.0
    assert holdings.unpriced_positions == 1
    assert holdings.items == []
    assert "Security not found for position 1" in caplog.text


@pytest.mark.anyio
async def test_total_and_holdings_agree_on_unpriced_account():
    """Both totals paths agree when a position is unpriced (shared loop)."""
    account = _account(uuid4(), "Unpriced Agreement")
    account.free_cash = 25.0
    account.net_deposits = 500.0

    priced_security = _security(uuid4(), "AAA")
    unpriced_security = _security(uuid4(), "BBB")
    priced = _position(1, account.id, priced_security.id, "10")
    priced.average_cost = Decimal("100.0")
    unpriced = _position(2, account.id, unpriced_security.id, "5")

    service = _build_multi_security_service(
        account,
        [priced, unpriced],
        {priced_security.id: priced_security, unpriced_security.id: unpriced_security},
        {priced_security.id: "110.0", unpriced_security.id: None},
    )

    totals = await service.get_total_for_account(account.id, Currency("USD"))
    holdings = await service.get_account_holdings(account.id)

    assert float(totals.value.amount) == holdings.total_value
    assert float(totals.profit_loss.amount) == holdings.total_profit_loss
    assert totals.unpriced_positions == holdings.unpriced_positions == 1
    assert totals.pricing_incomplete is holdings.pricing_incomplete is True
