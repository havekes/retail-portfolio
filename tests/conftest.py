"""Integration test fixtures using in-memory SQLite database."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

# Override database URL before importing app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from src.account.api_types import AccountTypeEnum
from src.account.enum import InstitutionEnum
from src.account.model import (
    AccountTypeModel,
    InstitutionModel,
)
from src.config.database import BaseModel, sessionmanager

# Import all fixtures from modules
from tests.fixtures.auth import *  # noqa: F401, F403
from tests.fixtures.account import *  # noqa: F401, F403
from tests.fixtures.market import *  # noqa: F401, F403


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
