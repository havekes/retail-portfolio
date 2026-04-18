"""Integration test fixtures using in-memory SQLite database."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

# Override database URL before importing app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "7bb26bc4200000a69d07fa542933ef7256c1e47462f9c5a2f9c1dcf562b482f9"
os.environ["ENVIRONMENT"] = "test"
os.environ["STUB_EXTERNAL_API"] = "true"

from src.account.api_types import AccountTypeEnum
from src.account.enum import InstitutionEnum
from src.account.model import (
    AccountTypeModel,
    InstitutionModel,
)
from src.config.database import BaseModel, sessionmanager
from src.ws.manager import ws_manager

# Import all fixtures from modules
from tests.fixtures.auth import *  # noqa: F401, F403
from tests.fixtures.account import *  # noqa: F401, F403
from tests.fixtures.market import *  # noqa: F401, F403

from unittest.mock import AsyncMock, MagicMock, patch

# Global mocks to prevent 4s teardown delay from Redis/Huey.
# These are applied once for the entire test session.
@pytest.fixture(scope="session", autouse=True)
def global_mocks():
    """Mock external dependencies (Redis, Huey) during tests.

    The critical fix here is patching `src.main.init_huey_dashboard` — NOT
    `huey_dashboard.init_huey_dashboard`. Because main.py binds the name at
    import time via `from huey_dashboard import init_huey_dashboard`, patching
    the original module has no effect. The real function creates a real
    AsyncRedis connection whose aclose() times out ~4 seconds per test.
    """
    from src.worker import huey

    # Force Huey into immediate mode so tasks run synchronously without Redis
    huey.immediate = True

    with (
        # Patch ws_manager methods on the singleton object
        patch.object(ws_manager, "init_redis", new=AsyncMock(return_value=None)),
        patch.object(ws_manager, "close", new=AsyncMock(return_value=None)),
        patch.object(ws_manager, "send_personal_message", new=AsyncMock(return_value=None)),
        patch.object(ws_manager, "send_personal_message_sync", return_value=None),
        # Patch the locally-bound name in src.main (this is what actually runs)
        patch("src.main.init_huey_dashboard", return_value=None),
    ):
        yield



@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Return in-memory SQLite database URL for testing."""
    return "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_engine(test_db_url: str) -> AsyncGenerator[AsyncEngine]:
    """Create test database engine and sync with sessionmanager."""
    # Use the sessionmanager's engine if it exists and is test database
    if sessionmanager._engine and "sqlite" in str(sessionmanager._engine.url):
        engine = sessionmanager._engine
    else:
        engine = create_async_engine(test_db_url, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)

    yield engine

    # Drop all tables (don't dispose since sessionmanager might still use it)
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)


@pytest.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide database session for tests."""
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def seed_reference_data(db_session: AsyncSession) -> None:
    """Seed reference data (account types, institutions) into test database."""
    # Add account types
    account_types = [
        AccountTypeModel(
            id=AccountTypeEnum.TFSA.value,
            name="TFSA",
            country="CA",
            tax_advantaged=True,
        ),
        AccountTypeModel(
            id=AccountTypeEnum.RRSP.value,
            name="RRSP",
            country="CA",
            tax_advantaged=True,
        ),
        AccountTypeModel(
            id=AccountTypeEnum.FHSA.value,
            name="FHSA",
            country="CA",
            tax_advantaged=True,
        ),
        AccountTypeModel(
            id=AccountTypeEnum.NON_REGISTERED.value,
            name="Non-Registered",
            country="CA",
            tax_advantaged=False,
        ),
    ]

    # Add institutions
    institutions = [
        InstitutionModel(
            id=InstitutionEnum.WEALTHSIMPLE.value,
            name="Wealthsimple",
            country="CA",
            is_active=True,
        ),
    ]

    db_session.add_all(account_types)
    db_session.add_all(institutions)
    await db_session.commit()
