import sys
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from src.commands.flush_market_data import flush_all, flush_security, main
from src.market.model import IntradayPriceModel, PriceModel, SecurityModel


async def _seed_security_and_prices(db_session):
    security = SecurityModel(
        id=uuid.uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        currency="USD",
        name="Apple Inc.",
    )
    db_session.add(security)
    await db_session.flush()

    price = PriceModel(
        security_id=security.id,
        date=date(2026, 1, 1),
        open=Decimal("150.0"),
        high=Decimal("152.0"),
        low=Decimal("149.0"),
        close=Decimal("151.0"),
        adjusted_close=Decimal("151.0"),
        volume=1000,
    )
    intraday = IntradayPriceModel(
        security_id=security.id,
        timestamp=datetime.now(UTC),
        open=Decimal("150.0"),
        high=Decimal("152.0"),
        low=Decimal("149.0"),
        close=Decimal("151.0"),
        volume=100,
    )
    db_session.add_all([price, intraday])
    await db_session.commit()
    return security


@pytest.mark.anyio
async def test_flush_security(db_session):
    security = await _seed_security_and_prices(db_session)
    mock_cache = AsyncMock()

    async def fake_factory():
        return mock_cache

    with (
        patch("src.commands.flush_market_data.input", return_value="y"),
        patch(
            "src.commands.flush_market_data.indicator_cache_factory",
            new=fake_factory,
        ),
    ):
        await flush_security(str(security.id))

    price_count = await db_session.scalar(
        select(func.count())
        .select_from(PriceModel)
        .where(PriceModel.security_id == security.id)
    )
    intraday_count = await db_session.scalar(
        select(func.count())
        .select_from(IntradayPriceModel)
        .where(IntradayPriceModel.security_id == security.id)
    )
    assert price_count == 0
    assert intraday_count == 0
    mock_cache.invalidate_security.assert_called_once_with(str(security.id))


@pytest.mark.anyio
async def test_flush_security_aborted(db_session):
    security = await _seed_security_and_prices(db_session)
    mock_cache = AsyncMock()

    async def fake_factory():
        return mock_cache

    with (
        patch("src.commands.flush_market_data.input", return_value="n"),
        patch(
            "src.commands.flush_market_data.indicator_cache_factory",
            new=fake_factory,
        ),
    ):
        await flush_security(str(security.id))

    price_count = await db_session.scalar(
        select(func.count())
        .select_from(PriceModel)
        .where(PriceModel.security_id == security.id)
    )
    assert price_count == 1
    mock_cache.invalidate_security.assert_not_called()


@pytest.mark.anyio
async def test_flush_all(db_session):
    await _seed_security_and_prices(db_session)
    mock_cache = AsyncMock()

    async def fake_factory():
        return mock_cache

    with (
        patch("src.commands.flush_market_data.input", return_value="y"),
        patch(
            "src.commands.flush_market_data.indicator_cache_factory",
            new=fake_factory,
        ),
    ):
        await flush_all()

    price_count = await db_session.scalar(select(func.count()).select_from(PriceModel))
    intraday_count = await db_session.scalar(
        select(func.count()).select_from(IntradayPriceModel)
    )
    assert price_count == 0
    assert intraday_count == 0
    mock_cache.flush_all.assert_called_once()


def test_main_all_flag():
    called = {}

    async def fake_flush_all():
        called["all"] = True

    test_args = ["flush_market_data.py", "--all"]
    with (
        patch.object(sys, "argv", test_args),
        patch("src.commands.flush_market_data.flush_all", new=fake_flush_all),
    ):
        main()

    assert called["all"] is True


def test_main_security_id_flag():
    security_id = str(uuid.uuid4())
    called = {}

    async def fake_flush_security(sid):
        called["security_id"] = sid

    test_args = ["flush_market_data.py", "--security-id", security_id]
    with (
        patch.object(sys, "argv", test_args),
        patch(
            "src.commands.flush_market_data.flush_security",
            new=fake_flush_security,
        ),
    ):
        main()

    assert called["security_id"] == security_id
