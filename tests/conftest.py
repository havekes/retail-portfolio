"""Integration test fixtures using PostgreSQL database."""

from collections.abc import AsyncGenerator, Generator
import os

import pytest
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

# Set default env vars before importing app
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

    from src.ws.manager import ConnectionManager

    with (
        # Patch ConnectionManager class methods so all loop-scoped instances are mocked
        patch.object(ConnectionManager, "init_redis", new=AsyncMock(return_value=None)),
        patch.object(ConnectionManager, "close", new=AsyncMock(return_value=None)),
        patch.object(ConnectionManager, "send_personal_message", new=AsyncMock(return_value=None)),
        patch.object(ConnectionManager, "send_personal_message_sync", return_value=None),
        # Patch the locally-bound name in src.main (this is what actually runs)
        patch("src.main.init_huey_dashboard", return_value=None),
    ):
        yield


@pytest.fixture(scope="session")
def postgres_service() -> Generator[str, None, None]:
    """Provide PostgreSQL connection URL, spinning up testcontainers if needed."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url and ("postgresql" in db_url or "postgres" in db_url):
        yield db_url
    else:
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:17-alpine") as postgres:
            url = make_url(postgres.get_connection_url()).set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
            os.environ["DATABASE_URL"] = url
            yield url


@pytest.fixture(scope="session")
def test_db_url(postgres_service: str) -> str:
    """Return PostgreSQL database URL for testing."""
    return postgres_service


@pytest.fixture(scope="function")
async def test_engine(test_db_url: str) -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine and sync with sessionmanager."""
    engine = create_async_engine(test_db_url, echo=False)

    # Rebind sessionmanager's engine and sessionmaker to point to the active test engine
    sessionmanager._engine = engine
    sessionmanager._sessionmaker = async_sessionmaker(
        autocommit=False, bind=engine, expire_on_commit=False
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)

    await engine.dispose()


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
