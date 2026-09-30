"""Unit tests for the user-wide holdings calculation in PositionService."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from currency_converter import CurrencyConverter
from stockholm import Currency

from src.account.api_types import AccountId
from src.account.repository import PositionRepository
from src.account.schema import AccountSchema, PositionSchema, UserHoldingRead
from src.account.service.account import AccountService
from src.account.service.position import PositionService
from src.core.enum import AccountTypeEnum, InstitutionEnum
from src.market.api import MarketPricesApi, SecurityApi
from src.market.api_types import Security
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


def _price(security_id) -> PriceSchema:
    return PriceSchema(
        security_id=security_id,
        date=date(2026, 1, 2),
        open=Decimal("100.0"),
        high=Decimal("100.0"),
        low=Decimal("100.0"),
        close=Decimal("100.0"),
        adjusted_close=Decimal("100.0"),
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
    from stockholm import Money
    market_prices.get_latest_close = AsyncMock(return_value=Money(100.0, "USD"))

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
