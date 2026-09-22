import datetime
import uuid
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.account.model import (
    AccountModel,
    PortfolioAccountModel,
    PortfolioModel,
    PositionModel,
)
from src.account.repository_sqlalchemy import (
    SqlAlchemyAccountRepository,
    SqlAlchemyPositionRepository,
)
from src.auth.model import UserModel
from src.auth.repository_sqlalchemy import (
    SqlAlchemyPasskeyRepository,
    SqlAlchemyRecoveryCodeRepository,
    SqlAlchemyTotpRepository,
    SqlAlchemyUserRepository,
)
from src.core.enum import AccountTypeEnum, InstitutionEnum
from src.market.api_types import IntradayPrice
from src.market.enum import WatchlistSortMode
from src.market.exception import (
    WatchlistDuplicateNameError,
    WatchlistNotFoundError,
)
from src.market.model import (
    PriceModel,
    SecurityModel,
    WatchlistModel,
    WatchlistsSecuritiesModel,
)
from src.market.repository_sqlalchemy import (
    SqlAlchemyIntradayPriceRepository,
    SqlAlchemyPriceRepository,
    SqlAlchemySecurityBrokerRepository,
    SqlAlchemySecurityRepository,
    SqlAlchemyWatchlistRepository,
)
from src.market.schema import (
    IntradayPriceSchema,
    PriceSchema,
    SecurityBrokerSchema,
    SecuritySchema,
    WatchlistSecuritySchema,
)


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

    user = await user_repo.create_user(
        "recovery_active_test@example.com", "password123"
    )

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
async def test_user_repository_update_last_login(db_session: AsyncSession):
    """Test update_last_login sets last_login_at timestamp on UserModel."""
    user_repo = SqlAlchemyUserRepository(db_session)
    user = await user_repo.create_user(
        "last_login_repo_test@example.com", "password123"
    )

    initial = await user_repo.get_by_id(user.id)
    assert initial is not None
    assert initial.last_login_at is None

    await user_repo.update_last_login(user.id)

    updated = await user_repo.get_by_id(user.id)
    assert updated is not None
    assert updated.last_login_at is not None


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

    user = await user_repo.create_user(
        "passkey_cascade_test@example.com", "password123"
    )
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


@pytest.mark.anyio
async def test_sqlalchemy_security_broker_repository_get_by_broker(
    db_session: AsyncSession,
):
    """Test get_by_broker returns None when absent and SecurityBrokerSchema when present."""
    security_repo = SqlAlchemySecurityRepository(db_session)
    broker_repo = SqlAlchemySecurityBrokerRepository(db_session)

    # 1. Non-existent mapping returns None
    missing = await broker_repo.get_by_broker(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="SHOP",
        broker_exchange="TSX",
    )
    assert missing is None

    # Create underlying security (required for foreign key)
    security = await security_repo.get_or_create(
        SecuritySchema(
            id=uuid.uuid4(),
            symbol="SHOP",
            exchange="TO",
            currency="CAD",
            name="Shopify Inc",
            isin="CA82509L1076",
            is_active=True,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
    )

    # 2. Create broker mapping
    created = await broker_repo.get_or_create(
        SecurityBrokerSchema(
            institution_id=InstitutionEnum.WEALTHSIMPLE,
            broker_symbol="SHOP",
            mapped_symbol="SHOP",
            broker_exchange="TSX",
            mapped_exchange="TO",
            broker_name="Shopify Inc",
            security_id=security.id,
            search_results=[],
        )
    )
    assert created.id is not None
    assert created.security_id == security.id

    # 3. Existing mapping returns matching SecurityBrokerSchema
    found = await broker_repo.get_by_broker(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="SHOP",
        broker_exchange="TSX",
    )
    assert found is not None
    assert found.id == created.id
    assert found.institution_id == InstitutionEnum.WEALTHSIMPLE
    assert found.broker_symbol == "SHOP"
    assert found.broker_exchange == "TSX"
    assert found.security_id == security.id

    # 4. Mismatched query fields return None
    assert (
        await broker_repo.get_by_broker(
            institution_id=InstitutionEnum.WEALTHSIMPLE,
            broker_symbol="OTHER",
            broker_exchange="TSX",
        )
        is None
    )
    assert (
        await broker_repo.get_by_broker(
            institution_id=InstitutionEnum.WEALTHSIMPLE,
            broker_symbol="SHOP",
            broker_exchange="NYSE",
        )
        is None
    )
    assert (
        await broker_repo.get_by_broker(
            institution_id=cast(InstitutionEnum, 999),
            broker_symbol="SHOP",
            broker_exchange="TSX",
        )
        is None
    )


@pytest.mark.anyio
async def test_account_repository_delete_cascades(
    db_session: AsyncSession, seed_reference_data: None
):
    """Test that SqlAlchemyAccountRepository.delete removes account, positions, and portfolio associations."""
    account_repo = SqlAlchemyAccountRepository(db_session)

    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    portfolio_id = uuid.uuid4()
    security_id = uuid.uuid4()

    account = AccountModel(
        id=account_id,
        external_id=str(uuid.uuid4()),
        name="Cascade Test Account",
        user_id=user_id,
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
    )
    db_session.add(account)

    portfolio = PortfolioModel(
        id=portfolio_id,
        user_id=user_id,
        name="Cascade Test Portfolio",
    )
    db_session.add(portfolio)

    portfolio_account = PortfolioAccountModel(
        portfolio_id=portfolio_id,
        account_id=account_id,
    )
    db_session.add(portfolio_account)

    position = PositionModel(
        account_id=account_id,
        security_id=security_id,
        quantity=Decimal("10.0"),
        average_cost=Decimal("150.0"),
    )
    db_session.add(position)

    await db_session.commit()

    # Verify rows exist before deletion
    assert await db_session.get(AccountModel, account_id) is not None
    pos_count_before = await db_session.scalar(
        select(func.count())
        .select_from(PositionModel)
        .where(PositionModel.account_id == account_id)
    )
    assert pos_count_before == 1
    pa_count_before = await db_session.scalar(
        select(func.count())
        .select_from(PortfolioAccountModel)
        .where(PortfolioAccountModel.account_id == account_id)
    )
    assert pa_count_before == 1

    # Delete via repository
    await account_repo.delete(account_id)

    # Verify rows are deleted
    assert await db_session.get(AccountModel, account_id) is None

    pos_count_after = await db_session.scalar(
        select(func.count())
        .select_from(PositionModel)
        .where(PositionModel.account_id == account_id)
    )
    assert pos_count_after == 0

    pa_count_after = await db_session.scalar(
        select(func.count())
        .select_from(PortfolioAccountModel)
        .where(PortfolioAccountModel.account_id == account_id)
    )
    assert pa_count_after == 0

    # Ensure portfolio itself was not deleted
    portfolio_in_db = await db_session.get(PortfolioModel, portfolio_id)
    assert portfolio_in_db is not None


def test_watchlist_sort_mode_enum_is_complete():
    """The sort enum exposes exactly the six modes the read contract advertises."""
    assert sorted(mode.value for mode in WatchlistSortMode) == [
        "custom",
        "date_added",
        "date_added_asc",
        "name_asc",
        "price_change_asc",
        "price_change_desc",
    ]


@pytest.mark.anyio
async def test_watchlist_repository_create_and_duplicate(db_session: AsyncSession):
    """Test create returns an empty watchlist and rejects duplicate names."""
    user_repo = SqlAlchemyUserRepository(db_session)
    watchlist_repo = SqlAlchemyWatchlistRepository(db_session)

    user = await user_repo.create_user(
        "watchlist_create_test@example.com", "password123"
    )

    created = await watchlist_repo.create(user.id, "Growth")
    assert created.name == "Growth"
    assert created.user_id == user.id
    assert created.sort == WatchlistSortMode.CUSTOM
    assert created.securities == []

    # The same name for the same user is rejected
    with pytest.raises(WatchlistDuplicateNameError):
        await watchlist_repo.create(user.id, "Growth")

    # Session remains usable after the rollback
    others = await watchlist_repo.get_by_user(user.id)
    assert [w.name for w in others] == ["Growth"]


@pytest.mark.anyio
async def test_watchlist_repository_rename(db_session: AsyncSession):
    """Test rename updates the name and enforces ownership + uniqueness."""
    user_repo = SqlAlchemyUserRepository(db_session)
    watchlist_repo = SqlAlchemyWatchlistRepository(db_session)

    user = await user_repo.create_user(
        "watchlist_rename_test@example.com", "password123"
    )
    other = await user_repo.create_user(
        "watchlist_rename_other@example.com", "password123"
    )

    created = await watchlist_repo.create(user.id, "Old Name")
    renamed = await watchlist_repo.rename(created.id, user.id, "New Name")
    assert renamed.id == created.id
    assert renamed.name == "New Name"

    # Duplicate name for the same user is rejected
    second = await watchlist_repo.create(user.id, "Second")
    with pytest.raises(WatchlistDuplicateNameError):
        await watchlist_repo.rename(second.id, user.id, "New Name")

    # Unknown watchlist id is not found
    with pytest.raises(WatchlistNotFoundError):
        await watchlist_repo.rename(uuid.uuid4(), user.id, "Whatever")

    # Another user's watchlist is not found
    with pytest.raises(WatchlistNotFoundError):
        await watchlist_repo.rename(created.id, other.id, "Stolen")


@pytest.mark.anyio
async def test_watchlist_repository_delete_cascades_membership(
    db_session: AsyncSession,
):
    """Test delete removes the watchlist and its membership rows."""
    user_repo = SqlAlchemyUserRepository(db_session)
    watchlist_repo = SqlAlchemyWatchlistRepository(db_session)

    user = await user_repo.create_user(
        "watchlist_delete_test@example.com", "password123"
    )
    created = await watchlist_repo.create(user.id, "To Delete")

    security = SecurityModel(
        id=uuid.uuid4(),
        symbol="CASCADE",
        exchange="US",
        currency="USD",
        name="Cascade Test Co",
        isin=None,
        is_active=True,
        updated_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(security)
    await db_session.flush()
    db_session.add(
        WatchlistsSecuritiesModel(
            watchlist_id=created.id,
            security_id=security.id,
            added_at=datetime.datetime.now(datetime.UTC),
            position=1,
        )
    )
    await db_session.commit()

    membership_before = await db_session.scalar(
        select(func.count())
        .select_from(WatchlistsSecuritiesModel)
        .where(WatchlistsSecuritiesModel.watchlist_id == created.id)
    )
    assert membership_before == 1

    await watchlist_repo.delete(created.id, user.id)

    assert (
        await db_session.scalar(
            select(WatchlistModel).where(WatchlistModel.id == created.id)
        )
        is None
    )
    membership_after = await db_session.scalar(
        select(func.count())
        .select_from(WatchlistsSecuritiesModel)
        .where(WatchlistsSecuritiesModel.watchlist_id == created.id)
    )
    assert membership_after == 0

    # Deleting another user's watchlist is a not-found
    other = await user_repo.create_user(
        "watchlist_delete_other@example.com", "password123"
    )
    other_watchlist = await watchlist_repo.create(other.id, "Other")
    with pytest.raises(WatchlistNotFoundError):
        await watchlist_repo.delete(other_watchlist.id, user.id)


@pytest.mark.anyio
async def test_watchlist_membership_position_and_added_at(
    db_session: AsyncSession,
):
    """Membership inserts append positions and stamp a tz-aware added_at."""
    user_repo = SqlAlchemyUserRepository(db_session)
    watchlist_repo = SqlAlchemyWatchlistRepository(db_session)

    user = await user_repo.create_user(
        "watchlist_position_test@example.com", "password123"
    )
    watchlist = await watchlist_repo.create(user.id, "Ordered")

    securities = [
        SecurityModel(
            id=uuid.uuid4(),
            symbol=f"POS{i}",
            exchange="US",
            currency="USD",
            name=f"Position Test {i}",
            isin=None,
            is_active=True,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        for i in range(3)
    ]
    db_session.add_all(securities)
    await db_session.flush()

    async def membership_rows() -> list[tuple[int, datetime.datetime]]:
        result = await db_session.execute(
            select(
                WatchlistsSecuritiesModel.position,
                WatchlistsSecuritiesModel.added_at,
            )
            .where(WatchlistsSecuritiesModel.watchlist_id == watchlist.id)
            .order_by(WatchlistsSecuritiesModel.position)
        )
        return [(position, added_at) for position, added_at in result.all()]

    # Positions are appended in add order; every membership gets an added_at.
    reads = [
        await watchlist_repo.add_security_to_watchlist(
            watchlist.id, user.id, security.id
        )
        for security in securities[:2]
    ]
    rows = await membership_rows()
    assert [position for position, _ in rows] == [1, 2]
    assert all(added_at is not None for _, added_at in rows)
    assert all(added_at.tzinfo is not None for _, added_at in rows)

    # The read schema carries the membership metadata, ordered by position.
    assert all(
        isinstance(security, WatchlistSecuritySchema) for security in reads[1].securities
    )
    assert [s.position for s in reads[1].securities] == [1, 2]
    assert [s.id for s in reads[1].securities] == [s.id for s in securities[:2]]
    assert all(s.added_at.tzinfo is not None for s in reads[1].securities)

    # Re-adding an existing membership is idempotent.
    await watchlist_repo.add_security_to_watchlist(
        watchlist.id, user.id, securities[0].id
    )
    assert [position for position, _ in await membership_rows()] == [1, 2]

    # Removing frees the position; re-adding appends after the current maximum.
    await watchlist_repo.remove_security_from_watchlist(
        watchlist.id, user.id, securities[0].id
    )
    refreshed = await watchlist_repo.add_security_to_watchlist(
        watchlist.id, user.id, securities[0].id
    )
    assert sorted(position for position, _ in await membership_rows()) == [2, 3]
    assert {s.id for s in refreshed.securities} == {
        securities[0].id,
        securities[1].id,
    }
    # Re-added membership sorts after the survivor, and metadata is still present.
    assert [s.id for s in refreshed.securities] == [securities[1].id, securities[0].id]
    assert [s.position for s in refreshed.securities] == [2, 3]
    assert all(s.added_at.tzinfo is not None for s in refreshed.securities)


@pytest.mark.anyio
async def test_watchlist_read_exposes_sort_and_ordered_membership_metadata(
    db_session: AsyncSession,
):
    """Every read path exposes ``sort`` and position-ordered membership metadata."""
    user_repo = SqlAlchemyUserRepository(db_session)
    watchlist_repo = SqlAlchemyWatchlistRepository(db_session)

    user = await user_repo.create_user(
        "watchlist_read_contract@example.com", "password123"
    )

    default = await watchlist_repo.create_default(user.id)
    assert default.sort == WatchlistSortMode.CUSTOM
    assert default.securities == []

    # Seed three memberships with deliberately out-of-order positions.
    securities = {
        position: SecurityModel(
            id=uuid.uuid4(),
            symbol=f"ORD{position}",
            exchange="US",
            currency="USD",
            name=f"Ordered {position}",
            isin=None,
            is_active=True,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        for position in (1, 2, 3)
    }
    db_session.add_all(securities.values())
    await db_session.flush()
    seeded_at = datetime.datetime.now(datetime.UTC)
    for position in (3, 1, 2):
        db_session.add(
            WatchlistsSecuritiesModel(
                watchlist_id=default.id,
                security_id=securities[position].id,
                added_at=seeded_at,
                position=position,
            )
        )
    await db_session.commit()

    def assert_read(read, expected_symbols: list[str]) -> None:
        assert [s.symbol for s in read.securities] == expected_symbols
        assert [s.position for s in read.securities] == [
            int(symbol.removeprefix("ORD")) for symbol in expected_symbols
        ]
        assert all(isinstance(s, WatchlistSecuritySchema) for s in read.securities)
        assert all(s.added_at.tzinfo is not None for s in read.securities)

    # get_by_user: sorted by position regardless of insert order.
    listed = await watchlist_repo.get_by_user(user.id)
    assert len(listed) == 1
    assert listed[0].sort == WatchlistSortMode.CUSTOM
    assert_read(listed[0], ["ORD1", "ORD2", "ORD3"])

    # rename
    renamed = await watchlist_repo.rename(default.id, user.id, "Renamed")
    assert renamed.name == "Renamed"
    assert_read(renamed, ["ORD1", "ORD2", "ORD3"])

    # add_security_to_watchlist appends after the current maximum position.
    fourth = SecurityModel(
        id=uuid.uuid4(),
        symbol="ORD4",
        exchange="US",
        currency="USD",
        name="Ordered 4",
        isin=None,
        is_active=True,
        updated_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(fourth)
    await db_session.flush()
    added = await watchlist_repo.add_security_to_watchlist(
        default.id, user.id, fourth.id
    )
    assert_read(added, ["ORD1", "ORD2", "ORD3", "ORD4"])

    # remove_security_from_watchlist drops the position-2 entry and keeps order.
    removed = await watchlist_repo.remove_security_from_watchlist(
        default.id, user.id, securities[2].id
    )
    assert_read(removed, ["ORD1", "ORD3", "ORD4"])

    # A non-default sort mode persisted on the model is surfaced on reads.
    watchlist_model = await db_session.get(WatchlistModel, default.id)
    assert watchlist_model is not None
    watchlist_model.sort = WatchlistSortMode.DATE_ADDED.value
    await db_session.commit()
    reselected = await watchlist_repo.get_by_user(user.id)
    assert reselected[0].sort == WatchlistSortMode.DATE_ADDED


@pytest.mark.anyio
async def test_watchlist_price_enrichment(db_session: AsyncSession):
    """Test watchlist security price enrichment for 0, 1, 2, 3+ prices, zero prev close, and batching."""
    user_repo = SqlAlchemyUserRepository(db_session)
    watchlist_repo = SqlAlchemyWatchlistRepository(db_session)

    user = await user_repo.create_user(
        "watchlist_prices_test@example.com", "password123"
    )

    # 1. Create test securities
    now = datetime.datetime.now(datetime.UTC)
    sec_zero = SecurityModel(
        id=uuid.uuid4(),
        symbol="ZERO",
        exchange="US",
        currency="USD",
        name="Zero Prices Corp",
        isin=None,
        is_active=True,
        updated_at=now,
    )
    sec_one = SecurityModel(
        id=uuid.uuid4(),
        symbol="ONE",
        exchange="US",
        currency="USD",
        name="One Price Inc",
        isin=None,
        is_active=True,
        updated_at=now,
    )
    sec_two = SecurityModel(
        id=uuid.uuid4(),
        symbol="TWO",
        exchange="US",
        currency="USD",
        name="Two Prices Ltd",
        isin=None,
        is_active=True,
        updated_at=now,
    )
    sec_multi = SecurityModel(
        id=uuid.uuid4(),
        symbol="MULTI",
        exchange="US",
        currency="USD",
        name="Multi Prices PLC",
        isin=None,
        is_active=True,
        updated_at=now,
    )
    sec_zero_prev = SecurityModel(
        id=uuid.uuid4(),
        symbol="ZEROPREV",
        exchange="US",
        currency="USD",
        name="Zero Prev Corp",
        isin=None,
        is_active=True,
        updated_at=now,
    )
    db_session.add_all([sec_zero, sec_one, sec_two, sec_multi, sec_zero_prev])
    await db_session.flush()

    # 2. Add market prices
    d1 = datetime.date(2024, 1, 1)
    d2 = datetime.date(2024, 1, 2)
    d3 = datetime.date(2024, 1, 3)

    prices = [
        # sec_one: 1 price
        PriceModel(
            security_id=sec_one.id,
            date=d1,
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("102.50"),
            adjusted_close=Decimal("102.50"),
            volume=1000,
        ),
        # sec_two: 2 prices (d1 = 50.00, d2 = 55.00)
        PriceModel(
            security_id=sec_two.id,
            date=d1,
            open=Decimal("49"),
            high=Decimal("51"),
            low=Decimal("48"),
            close=Decimal("50.00"),
            adjusted_close=Decimal("50.00"),
            volume=2000,
        ),
        PriceModel(
            security_id=sec_two.id,
            date=d2,
            open=Decimal("51"),
            high=Decimal("56"),
            low=Decimal("50"),
            close=Decimal("55.00"),
            adjusted_close=Decimal("55.00"),
            volume=2500,
        ),
        # sec_multi: 3 prices (d1 = 10.00, d2 = 20.00, d3 = 15.00)
        PriceModel(
            security_id=sec_multi.id,
            date=d1,
            open=Decimal("10"),
            high=Decimal("11"),
            low=Decimal("9"),
            close=Decimal("10.00"),
            adjusted_close=Decimal("10.00"),
            volume=500,
        ),
        PriceModel(
            security_id=sec_multi.id,
            date=d2,
            open=Decimal("11"),
            high=Decimal("21"),
            low=Decimal("10"),
            close=Decimal("20.00"),
            adjusted_close=Decimal("20.00"),
            volume=800,
        ),
        PriceModel(
            security_id=sec_multi.id,
            date=d3,
            open=Decimal("19"),
            high=Decimal("20"),
            low=Decimal("14"),
            close=Decimal("15.00"),
            adjusted_close=Decimal("15.00"),
            volume=1200,
        ),
        # sec_zero_prev: 2 prices with prev close = 0
        PriceModel(
            security_id=sec_zero_prev.id,
            date=d1,
            open=Decimal("0"),
            high=Decimal("0"),
            low=Decimal("0"),
            close=Decimal("0.00"),
            adjusted_close=Decimal("0.00"),
            volume=0,
        ),
        PriceModel(
            security_id=sec_zero_prev.id,
            date=d2,
            open=Decimal("40"),
            high=Decimal("45"),
            low=Decimal("39"),
            close=Decimal("42.00"),
            adjusted_close=Decimal("42.00"),
            volume=1500,
        ),
    ]
    db_session.add_all(prices)
    await db_session.flush()

    # 3. Create watchlist and attach securities
    wl = await watchlist_repo.create(user.id, "All Metrics")
    for sec in [sec_zero, sec_one, sec_two, sec_multi, sec_zero_prev]:
        await watchlist_repo.add_security_to_watchlist(wl.id, user.id, sec.id)

    # 4. Verify get_by_user returns enriched securities
    watchlists = await watchlist_repo.get_by_user(user.id)
    assert len(watchlists) == 1
    sec_map = {s.symbol: s for s in watchlists[0].securities}

    # sec_zero: 0 prices
    assert sec_map["ZERO"].current_price is None
    assert sec_map["ZERO"].daily_price_change is None
    assert sec_map["ZERO"].daily_price_change_percent is None

    # sec_one: 1 price
    assert sec_map["ONE"].current_price == Decimal("102.50")
    assert sec_map["ONE"].daily_price_change is None
    assert sec_map["ONE"].daily_price_change_percent is None

    # sec_two: 2 prices (latest 55.00, prev 50.00)
    assert sec_map["TWO"].current_price == Decimal("55.00")
    assert sec_map["TWO"].daily_price_change == Decimal("5.00")
    assert sec_map["TWO"].daily_price_change_percent == Decimal("10.0")

    # sec_multi: 3 prices (latest 15.00, prev 20.00; d1 10.00 ignored)
    assert sec_map["MULTI"].current_price == Decimal("15.00")
    assert sec_map["MULTI"].daily_price_change == Decimal("-5.00")
    assert sec_map["MULTI"].daily_price_change_percent == Decimal("-25.0")

    # sec_zero_prev: prev.close is 0 (latest 42.00, prev 0.00) -> daily_price_change_percent is None
    assert sec_map["ZEROPREV"].current_price == Decimal("42.00")
    assert sec_map["ZEROPREV"].daily_price_change == Decimal("42.00")
    assert sec_map["ZEROPREV"].daily_price_change_percent is None

    # 5. Verify get_securities returns same enrichments
    paged_secs, total = await watchlist_repo.get_securities(wl.id, user.id)
    assert total == 5
    paged_map = {s.symbol: s for s in paged_secs}
    assert paged_map["TWO"].current_price == Decimal("55.00")
    assert paged_map["TWO"].daily_price_change == Decimal("5.00")
    assert paged_map["TWO"].daily_price_change_percent == Decimal("10.0")

    # 6. Verify remove_security_from_watchlist retains enrichment on remaining securities
    updated_wl = await watchlist_repo.remove_security_from_watchlist(
        wl.id, user.id, sec_zero.id
    )
    assert len(updated_wl.securities) == 4
    updated_map = {s.symbol: s for s in updated_wl.securities}
    assert updated_map["MULTI"].current_price == Decimal("15.00")
    assert updated_map["MULTI"].daily_price_change == Decimal("-5.00")


@pytest.mark.anyio
async def test_position_repository_get_by_user_scopes_and_paginates(
    db_session: AsyncSession,
    test_accounts,
    other_user_account,
    test_security,
):
    """get_by_user returns only the user's positions with a full count."""
    repo = SqlAlchemyPositionRepository(db_session)

    for account in test_accounts:
        db_session.add(
            PositionModel(
                account_id=account.id,
                security_id=test_security.id,
                quantity=Decimal("1.0"),
                average_cost=Decimal("1.0"),
            )
        )
    # A position owned by a different user must never be returned.
    db_session.add(
        PositionModel(
            account_id=other_user_account.id,
            security_id=test_security.id,
            quantity=Decimal("99.0"),
            average_cost=Decimal("99.0"),
        )
    )
    await db_session.commit()

    user_id = test_accounts[0].user_id
    positions, total = await repo.get_by_user(user_id)
    assert total == 3
    assert len(positions) == 3
    own_account_ids = {account.id for account in test_accounts}
    assert {position.account_id for position in positions} == own_account_ids

    page, page_total = await repo.get_by_user(user_id, offset=1, limit=1)
    assert page_total == 3
    assert len(page) == 1

    other_positions, other_total = await repo.get_by_user(other_user_account.user_id)
    assert other_total == 1
    assert len(other_positions) == 1
    assert other_positions[0].account_id == other_user_account.id
