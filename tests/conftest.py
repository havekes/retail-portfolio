import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from src.models import Base
from src import database


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(request):
    """Set up an in-memory SQLite database for tests."""

    async def _setup():
        # Create async engine for tests
        test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        # Create all tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Override the global sessionmanager with the test database
        database.sessionmanager = database.DatabaseSessionManager(TEST_DATABASE_URL, {"echo": False})

    asyncio.run(_setup())

    # Add finalizer to close the sessionmanager
    def teardown():
        asyncio.run(database.sessionmanager.close())

    request.addfinalizer(teardown)
