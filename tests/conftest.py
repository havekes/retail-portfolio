import asyncio
import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from src.models import Base
from src import database

# Override DATABASE_URL for tests to use in-memory SQLite
os.environ['DATABASE_URL'] = "sqlite+aiosqlite:///:memory:"
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(request):
    """Create all database tables for tests."""

    async def _setup():
        # Create async engine for tests
        test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        # Create all tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())

    # Add finalizer to close the sessionmanager
    def teardown():
        asyncio.run(database.sessionmanager.close())

    request.addfinalizer(teardown)
