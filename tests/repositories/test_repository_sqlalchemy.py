import datetime
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.market.api_types import IntradayPrice
from src.market.repository_sqlalchemy import (
    SqlAlchemyIntradayPriceRepository,
    SqlAlchemyPriceRepository,
    SqlAlchemySecurityRepository,
)
from src.market.schema import IntradayPriceSchema, PriceSchema, SecuritySchema


@pytest.mark.anyio
async def test_save_prices_upserts_correctly(db_session: AsyncSession):
    """
    Test that save_prices gracefully handles existing records by updating them
    instead of throwing a unique constraint violation.
    """
    security_repo = SqlAlchemySecurityRepository(db_session)
    price_repo = SqlAlchemyPriceRepository(db_session)

    # Create an active security in the DB
    security_schema = SecuritySchema(
        id=uuid.uuid4(),
        symbol="TEST",
        exchange="US",
        currency="USD",
        name="Test Company",
        isin=None,
        is_active=True,
        updated_at=datetime.datetime.now(datetime.UTC),
    )
    security = await security_repo.get_or_create(security_schema)
    assert security.id is not None

    test_date = datetime.date(2023, 1, 1)

    initial_price = PriceSchema(
        security_id=security.id,
        date=test_date,
        open=Decimal("100.0"),
        high=Decimal("105.0"),
        low=Decimal("95.0"),
        close=Decimal("100.0"),
        adjusted_close=Decimal("100.0"),
        volume=1000,
    )

    # Insert initial price
    saved_initial = await price_repo.save_prices([initial_price])
    assert len(saved_initial) == 1
    assert saved_initial[0].close == Decimal("100.0")

    # Update price for the SAME security and date
    updated_price = PriceSchema(
        security_id=security.id,
        date=test_date,
        open=Decimal("100.0"),
        high=Decimal("110.0"),  # Changed
        low=Decimal("95.0"),
        close=Decimal("108.0"),  # Changed
        adjusted_close=Decimal("108.0"),  # Changed
        volume=2000,  # Changed
    )

    saved_updated = await price_repo.save_prices([updated_price])
    assert len(saved_updated) == 1

    # Verify the upsert succeeded
    assert saved_updated[0].high == Decimal("110.0")
    assert saved_updated[0].close == Decimal("108.0")
    assert saved_updated[0].volume == 2000

    # Verify that we didn't just append a new row, but updated the existing one
    prices_on_date, _ = await price_repo.get_prices(
        security, from_date=test_date, to_date=test_date
    )
    assert len(prices_on_date) == 1
    assert prices_on_date[0].close == Decimal("108.0")


@pytest.mark.anyio
async def test_save_prices_large_batch(db_session: AsyncSession):
    """
    Test that save_prices handles a large number of rows that would normally
    exceed the asyncpg query parameter limit (32767).
    """
    security_repo = SqlAlchemySecurityRepository(db_session)
    price_repo = SqlAlchemyPriceRepository(db_session)

    # Create an active security in the DB
    security_schema = SecuritySchema(
        id=uuid.uuid4(),
        symbol="LARGE",
        exchange="US",
        currency="USD",
        name="Large Batch Test",
        isin=None,
        is_active=True,
        updated_at=datetime.datetime.now(datetime.UTC),
    )
    security = await security_repo.get_or_create(security_schema)

    # Create 5000 price records.
    # Each record has ~8 fields (security_id, date, open, high, low, close, adjusted_close, volume).
    # 5000 * 8 = 40,000 parameters, which exceeds 32,767.
    num_rows = 5000
    base_date = datetime.date(2000, 1, 1)
    prices = []
    for i in range(num_rows):
        prices.append(
            PriceSchema(
                security_id=security.id,
                date=base_date + datetime.timedelta(days=i),
                open=Decimal("100.0"),
                high=Decimal("105.0"),
                low=Decimal("95.0"),
                close=Decimal("100.0"),
                adjusted_close=Decimal("100.0"),
                volume=1000,
            )
        )

    # This should succeed due to chunking
    saved_prices = await price_repo.save_prices(prices)

    assert len(saved_prices) == num_rows

    # Verify a few records
    prices_in_db, _ = await price_repo.get_prices(
        security,
        from_date=base_date,
        to_date=base_date + datetime.timedelta(days=num_rows - 1),
        limit=10000,
    )
    assert len(prices_in_db) == num_rows


@pytest.mark.anyio
async def test_intraday_repository_save_and_retrieve(db_session: AsyncSession):
    """Test saving single and batch 1-hour candles and querying by time range."""
    security_repo = SqlAlchemySecurityRepository(db_session)
    intraday_repo = SqlAlchemyIntradayPriceRepository(db_session)

    security = await security_repo.get_or_create(
        SecuritySchema(
            id=uuid.uuid4(),
            symbol="AAPL",
            exchange="US",
            currency="USD",
            name="Apple Inc",
            isin=None,
            is_active=True,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
    )

    base_time = datetime.datetime(2026, 1, 15, 9, 30, tzinfo=datetime.UTC)

    # Test save_intraday_price (single)
    single_candle = IntradayPriceSchema(
        security_id=security.id,
        timestamp=base_time,
        open=Decimal("150.0"),
        high=Decimal("152.5"),
        low=Decimal("149.5"),
        close=Decimal("151.0"),
        volume=5000,
    )
    saved_single = await intraday_repo.save_intraday_price(single_candle)
    assert saved_single.id is not None
    assert saved_single.close == Decimal("151.0")

    # Test save_intraday_prices (batch)
    batch_candles = [
        IntradayPriceSchema(
            security_id=security.id,
            timestamp=base_time + datetime.timedelta(hours=i),
            open=Decimal("150.0") + Decimal(i),
            high=Decimal("153.0") + Decimal(i),
            low=Decimal("149.0") + Decimal(i),
            close=Decimal("152.0") + Decimal(i),
            volume=6000 + i * 100,
        )
        for i in range(1, 5)
    ]
    saved_batch = await intraday_repo.save_intraday_prices(batch_candles)
    assert len(saved_batch) == 4

    # Query all intraday prices for security
    all_candles, total_count = await intraday_repo.get_intraday_prices(security.id)
    assert total_count == 5
    assert len(all_candles) == 5
    assert all_candles[0].timestamp == base_time

    # Query range
    start_range = base_time + datetime.timedelta(hours=1)
    end_range = base_time + datetime.timedelta(hours=3)
    ranged_candles, total_count = await intraday_repo.get_intraday_prices(
        security.id, start_time=start_range, end_time=end_range
    )
    assert total_count == 3
    assert len(ranged_candles) == 3
    assert ranged_candles[0].timestamp == start_range
    assert ranged_candles[-1].timestamp == end_range


@pytest.mark.anyio
async def test_intraday_repository_unique_constraint(db_session: AsyncSession):
    """Test unique constraint on (security_id, timestamp) and upsert logic."""
    security_repo = SqlAlchemySecurityRepository(db_session)
    intraday_repo = SqlAlchemyIntradayPriceRepository(db_session)

    security = await security_repo.get_or_create(
        SecuritySchema(
            id=uuid.uuid4(),
            symbol="MSFT",
            exchange="US",
            currency="USD",
            name="Microsoft Corp",
            isin=None,
            is_active=True,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
    )

    test_time = datetime.datetime(2026, 2, 1, 10, 0, tzinfo=datetime.UTC)

    candle_v1 = IntradayPriceSchema(
        security_id=security.id,
        timestamp=test_time,
        open=Decimal("300.0"),
        high=Decimal("305.0"),
        low=Decimal("298.0"),
        close=Decimal("302.0"),
        volume=10000,
    )
    await intraday_repo.save_intraday_prices([candle_v1])

    # Upsert with updated values for same (security_id, timestamp)
    candle_v2 = IntradayPriceSchema(
        security_id=security.id,
        timestamp=test_time,
        open=Decimal("300.0"),
        high=Decimal("310.0"),  # updated
        low=Decimal("298.0"),
        close=Decimal("309.0"),  # updated
        volume=15000,  # updated
    )
    updated = await intraday_repo.save_intraday_prices([candle_v2])
    assert len(updated) == 1
    assert updated[0].high == Decimal("310.0")
    assert updated[0].close == Decimal("309.0")
    assert updated[0].volume == 15000

    candles_in_db, _ = await intraday_repo.get_intraday_prices(security.id)
    assert len(candles_in_db) == 1
    assert candles_in_db[0].close == Decimal("309.0")


@pytest.mark.anyio
async def test_intraday_and_daily_price_isolation(db_session: AsyncSession):
    """Test that intraday price records do not interfere with daily price records."""
    security_repo = SqlAlchemySecurityRepository(db_session)
    price_repo = SqlAlchemyPriceRepository(db_session)
    intraday_repo = SqlAlchemyIntradayPriceRepository(db_session)

    security = await security_repo.get_or_create(
        SecuritySchema(
            id=uuid.uuid4(),
            symbol="NVDA",
            exchange="US",
            currency="USD",
            name="NVIDIA Corp",
            isin=None,
            is_active=True,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
    )

    test_date = datetime.date(2026, 3, 1)
    daily_price = PriceSchema(
        security_id=security.id,
        date=test_date,
        open=Decimal("500.0"),
        high=Decimal("520.0"),
        low=Decimal("495.0"),
        close=Decimal("515.0"),
        adjusted_close=Decimal("515.0"),
        volume=25000,
    )
    await price_repo.save_prices([daily_price])

    intraday_candle = IntradayPriceSchema(
        security_id=security.id,
        timestamp=datetime.datetime(2026, 3, 1, 14, 0, tzinfo=datetime.UTC),
        open=Decimal("505.0"),
        high=Decimal("510.0"),
        low=Decimal("502.0"),
        close=Decimal("508.0"),
        volume=3000,
    )
    await intraday_repo.save_intraday_price(intraday_candle)

    daily_prices, count = await price_repo.get_prices(
        security, from_date=test_date, to_date=test_date
    )
    assert count == 1
    assert len(daily_prices) == 1
    assert daily_prices[0].close == Decimal("515.0")

    intraday_prices, _ = await intraday_repo.get_intraday_prices(security.id)
    assert len(intraday_prices) == 1
    assert intraday_prices[0].close == Decimal("508.0")


def test_intraday_schema_requires_timezone_aware_datetime():
    """Test that IntradayPriceSchema and IntradayPrice reject naive datetimes."""
    security_id = uuid.uuid4()
    naive_dt = datetime.datetime(2026, 1, 15, 9, 30)  # noqa: DTZ001

    with pytest.raises(ValidationError):
        IntradayPriceSchema(
            security_id=security_id,
            timestamp=naive_dt,
            open=Decimal("100.0"),
            high=Decimal("105.0"),
            low=Decimal("99.0"),
            close=Decimal("102.0"),
            volume=1000,
        )

    with pytest.raises(ValidationError):
        IntradayPrice(
            security_id=security_id,
            timestamp=naive_dt,
            open=Decimal("100.0"),
            high=Decimal("105.0"),
            low=Decimal("99.0"),
            close=Decimal("102.0"),
            volume=1000,
        )


@pytest.mark.anyio
async def test_intraday_repository_single_save_upsert(db_session: AsyncSession):
    """Test that save_intraday_price gracefully updates existing records on conflict."""
    security_repo = SqlAlchemySecurityRepository(db_session)
    intraday_repo = SqlAlchemyIntradayPriceRepository(db_session)

    security = await security_repo.get_or_create(
        SecuritySchema(
            id=uuid.uuid4(),
            symbol="AMZN",
            exchange="US",
            currency="USD",
            name="Amazon.com Inc",
            isin=None,
            is_active=True,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
    )

    test_time = datetime.datetime(2026, 2, 10, 11, 0, tzinfo=datetime.UTC)

    candle_v1 = IntradayPriceSchema(
        security_id=security.id,
        timestamp=test_time,
        open=Decimal("180.0"),
        high=Decimal("185.0"),
        low=Decimal("179.0"),
        close=Decimal("182.0"),
        volume=5000,
    )
    saved1 = await intraday_repo.save_intraday_price(candle_v1)
    assert saved1.close == Decimal("182.0")

    candle_v2 = IntradayPriceSchema(
        security_id=security.id,
        timestamp=test_time,
        open=Decimal("180.0"),
        high=Decimal("188.0"),
        low=Decimal("179.0"),
        close=Decimal("187.0"),
        volume=8000,
    )
    saved2 = await intraday_repo.save_intraday_price(candle_v2)
    assert saved2.close == Decimal("187.0")

    candles_in_db, _ = await intraday_repo.get_intraday_prices(security.id)
    assert len(candles_in_db) == 1
    assert candles_in_db[0].close == Decimal("187.0")
    assert candles_in_db[0].high == Decimal("188.0")

