import datetime
from decimal import Decimal
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.market.repository_sqlalchemy import (
    SqlAlchemyPriceRepository,
    SqlAlchemySecurityRepository,
)
from src.market.schema import PriceSchema, SecuritySchema


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
        close=Decimal("108.0"), # Changed
        adjusted_close=Decimal("108.0"), # Changed
        volume=2000, # Changed
    )

    saved_updated = await price_repo.save_prices([updated_price])
    assert len(saved_updated) == 1
    
    # Verify the upsert succeeded
    assert saved_updated[0].high == Decimal("110.0")
    assert saved_updated[0].close == Decimal("108.0")
    assert saved_updated[0].volume == 2000
    
    # Verify that we didn't just append a new row, but updated the existing one
    prices_on_date = await price_repo.get_prices(security, from_date=test_date, to_date=test_date)
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
    prices_in_db = await price_repo.get_prices(
        security,
        from_date=base_date,
        to_date=base_date + datetime.timedelta(days=num_rows - 1),
    )
    assert len(prices_in_db) == num_rows
