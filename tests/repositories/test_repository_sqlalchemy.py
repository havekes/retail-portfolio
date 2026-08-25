import datetime
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.model import UserModel
from src.auth.repository_sqlalchemy import (
    SqlAlchemyPasskeyRepository,
    SqlAlchemyRecoveryCodeRepository,
    SqlAlchemyTotpRepository,
    SqlAlchemyUserRepository,
)
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
    all_candles = await intraday_repo.get_intraday_prices(security.id)
    assert len(all_candles) == 5
    assert all_candles[0].timestamp == base_time

    # Query range
    start_range = base_time + datetime.timedelta(hours=1)
    end_range = base_time + datetime.timedelta(hours=3)
    ranged_candles = await intraday_repo.get_intraday_prices(
        security.id, start_time=start_range, end_time=end_range
    )
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

    candles_in_db = await intraday_repo.get_intraday_prices(security.id)
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

    intraday_prices = await intraday_repo.get_intraday_prices(security.id)
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

    candles_in_db = await intraday_repo.get_intraday_prices(security.id)
    assert len(candles_in_db) == 1
    assert candles_in_db[0].close == Decimal("187.0")
    assert candles_in_db[0].high == Decimal("188.0")


@pytest.mark.anyio
async def test_totp_repository_crud(db_session: AsyncSession):
    """Test CRUD operations for SqlAlchemyTotpRepository."""
    user_repo = SqlAlchemyUserRepository(db_session)
    totp_repo = SqlAlchemyTotpRepository(db_session)

    user = await user_repo.create_user("totp_repo_test@example.com", "password123")

    # Initial get returns None
    assert await totp_repo.get_by_user_id(user.id) is None

    # Create TOTP
    secret = "JBSWY3DPEHPK3PXP"
    created = await totp_repo.create_or_update(user.id, secret)
    assert created.user_id == user.id
    assert created.secret == secret
    assert created.is_verified is False

    # Get by user_id
    retrieved = await totp_repo.get_by_user_id(user.id)
    assert retrieved is not None
    assert retrieved.secret == secret
    assert retrieved.is_verified is False

    # Mark as verified
    await totp_repo.mark_as_verified(user.id)
    verified = await totp_repo.get_by_user_id(user.id)
    assert verified is not None
    assert verified.is_verified is True

    # Update secret (resets is_verified)
    new_secret = "HXDMVJECJJWSRB3H"
    updated = await totp_repo.create_or_update(user.id, new_secret)
    assert updated.secret == new_secret
    assert updated.is_verified is False

    # Delete TOTP
    await totp_repo.delete_by_user_id(user.id)
    assert await totp_repo.get_by_user_id(user.id) is None


@pytest.mark.anyio
async def test_recovery_code_repository_crud(db_session: AsyncSession):
    """Test CRUD operations for SqlAlchemyRecoveryCodeRepository."""
    user_repo = SqlAlchemyUserRepository(db_session)
    recovery_repo = SqlAlchemyRecoveryCodeRepository(db_session)

    user = await user_repo.create_user("recovery_repo_test@example.com", "password123")

    # Initially 0 active codes
    assert await recovery_repo.count_active_by_user_id(user.id) == 0
    assert await recovery_repo.get_by_user_id(user.id) == []

    # Create recovery codes
    fake_hashes = [f"hash_{i}" for i in range(8)]
    created = await recovery_repo.create_recovery_codes(user.id, fake_hashes)
    assert len(created) == 8
    assert all(c.user_id == user.id for c in created)
    assert all(c.is_used is False for c in created)

    # Count active codes
    assert await recovery_repo.count_active_by_user_id(user.id) == 8

    # Get all by user id
    all_codes = await recovery_repo.get_by_user_id(user.id)
    assert len(all_codes) == 8

    # Delete recovery codes
    await recovery_repo.delete_by_user_id(user.id)
    assert await recovery_repo.count_active_by_user_id(user.id) == 0
    assert await recovery_repo.get_by_user_id(user.id) == []


@pytest.mark.anyio
async def test_recovery_code_repository_active_and_mark_as_used(
    db_session: AsyncSession,
):
    """Test get_active_by_user_id and mark_as_used methods."""
    user_repo = SqlAlchemyUserRepository(db_session)
    recovery_repo = SqlAlchemyRecoveryCodeRepository(db_session)

    user = await user_repo.create_user("recovery_active_test@example.com", "password123")

    fake_hashes = ["hash_1", "hash_2", "hash_3"]
    created = await recovery_repo.create_recovery_codes(user.id, fake_hashes)
    assert len(created) == 3

    # Initially all 3 are active
    active = await recovery_repo.get_active_by_user_id(user.id)
    assert len(active) == 3
    assert {c.code_hash for c in active} == {"hash_1", "hash_2", "hash_3"}

    # Mark the first code as used
    code_to_use = active[0]
    await recovery_repo.mark_as_used(code_to_use.id)

    # Active now only returns 2
    active_after = await recovery_repo.get_active_by_user_id(user.id)
    assert len(active_after) == 2
    assert code_to_use.id not in [c.id for c in active_after]
    assert await recovery_repo.count_active_by_user_id(user.id) == 2

    # All codes still returns 3, with one marked used and timestamped
    all_codes = await recovery_repo.get_by_user_id(user.id)
    assert len(all_codes) == 3
    used_code = next(c for c in all_codes if c.id == code_to_use.id)
    assert used_code.is_used is True
    assert used_code.used_at is not None


@pytest.mark.anyio
async def test_totp_and_recovery_cascade_on_user_delete(db_session: AsyncSession):
    """Test that deleting a user cascades to their TOTP and recovery codes."""
    from sqlalchemy import delete

    user_repo = SqlAlchemyUserRepository(db_session)
    totp_repo = SqlAlchemyTotpRepository(db_session)
    recovery_repo = SqlAlchemyRecoveryCodeRepository(db_session)

    user = await user_repo.create_user("cascade_test@example.com", "password123")
    await totp_repo.create_or_update(user.id, "JBSWY3DPEHPK3PXP")
    await recovery_repo.create_recovery_codes(user.id, ["hash1", "hash2"])

    assert await totp_repo.get_by_user_id(user.id) is not None
    assert await recovery_repo.count_active_by_user_id(user.id) == 2

    # Delete user directly
    await db_session.execute(delete(UserModel).where(UserModel.id == user.id))
    await db_session.commit()

    assert await totp_repo.get_by_user_id(user.id) is None
    assert await recovery_repo.count_active_by_user_id(user.id) == 0


@pytest.mark.anyio
async def test_passkey_repository_crud(db_session: AsyncSession):
    """Test full CRUD operations on PasskeyRepository."""
    user_repo = SqlAlchemyUserRepository(db_session)
    passkey_repo = SqlAlchemyPasskeyRepository(db_session)

    user = await user_repo.create_user("passkey_repo_test@example.com", "password123")

    cred_id = b"test_credential_id_bytes_123"
    pub_key = b"test_public_key_bytes_456"

    # Create
    created = await passkey_repo.create_passkey(
        user.id,
        credential_id=cred_id,
        public_key=pub_key,
        sign_count=0,
        name="MacBook Touch ID",
        transports=["internal", "hybrid"],
    )
    assert created.id is not None
    assert created.user_id == user.id
    assert created.credential_id == cred_id
    assert created.public_key == pub_key
    assert created.sign_count == 0
    assert created.name == "MacBook Touch ID"
    assert created.transports == ["internal", "hybrid"]
    assert created.last_used_at is None

    # Get by ID
    by_id = await passkey_repo.get_by_id(created.id)
    assert by_id is not None
    assert by_id.id == created.id
    assert by_id.name == "MacBook Touch ID"

    # Get by credential ID
    by_cred = await passkey_repo.get_by_credential_id(cred_id)
    assert by_cred is not None
    assert by_cred.id == created.id

    # Get by user ID
    user_passkeys = await passkey_repo.get_by_user_id(user.id)
    assert len(user_passkeys) == 1
    assert user_passkeys[0].id == created.id

    # Update name
    updated = await passkey_repo.update_name(created.id, "Work MacBook")
    assert updated is not None
    assert updated.name == "Work MacBook"

    # Update sign count and last used
    now = datetime.datetime.now(datetime.UTC)
    await passkey_repo.update_sign_count_and_last_used(
        created.id, sign_count=5, last_used_at=now
    )
    refreshed = await passkey_repo.get_by_id(created.id)
    assert refreshed is not None
    assert refreshed.sign_count == 5
    assert refreshed.last_used_at is not None

    # Delete with non-matching user returns False
    fake_user_id = uuid.uuid4()
    assert await passkey_repo.delete_by_id(created.id, fake_user_id) is False
    assert await passkey_repo.get_by_id(created.id) is not None

    # Delete with matching user returns True
    assert await passkey_repo.delete_by_id(created.id, user.id) is True
    assert await passkey_repo.get_by_id(created.id) is None


@pytest.mark.anyio
async def test_passkey_cascade_on_user_delete(db_session: AsyncSession):
    """Test that deleting a user cascades to their passkeys."""
    from sqlalchemy import delete

    user_repo = SqlAlchemyUserRepository(db_session)
    passkey_repo = SqlAlchemyPasskeyRepository(db_session)

    user = await user_repo.create_user("passkey_cascade_test@example.com", "password123")
    passkey = await passkey_repo.create_passkey(
        user.id,
        credential_id=b"cascade_cred_id",
        public_key=b"cascade_pub_key",
        sign_count=0,
        name="YubiKey",
    )

    assert await passkey_repo.get_by_id(passkey.id) is not None

    # Delete user
    await db_session.execute(delete(UserModel).where(UserModel.id == user.id))
    await db_session.commit()

    assert await passkey_repo.get_by_id(passkey.id) is None



