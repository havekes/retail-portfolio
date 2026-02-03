"""Market data and EODHD API mocking fixtures."""

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.api import UserApi
from src.auth.repository_sqlalchemy import SqlAlchemyUserRepository
from src.auth.schema import UserSchema
from src.main import app
from src.market.api_types import EodhdSearchResult, HistoricalPrice
from src.market.schema import SecuritySchema


class MockEodhdGateway:
    """Mock implementation of EodhdGateway for testing."""

    def search(self, query: str) -> list[EodhdSearchResult]:  # noqa: ARG002
        """Return empty search results."""
        return []

    def get_price_on_date(
        self, security: SecuritySchema, date: object  # noqa: ARG002
    ) -> HistoricalPrice | None:
        """Return empty price result."""
        return None

    def get_prices(
        self, security: SecuritySchema, from_date: object, to_date: object  # noqa: ARG002
    ) -> list[HistoricalPrice]:
        """Return empty price list."""
        return []


@pytest.fixture
def mock_eodhd_gateway() -> MockEodhdGateway:
    """Provide a mock EODHD gateway that returns empty payloads."""
    return MockEodhdGateway()


@pytest.fixture
def mock_eodhd_gateway_factory(mock_eodhd_gateway: MockEodhdGateway, monkeypatch):
    """Patch the EODHD gateway factory to return the mock gateway."""
    from src.market import api

    def mock_factory():
        return mock_eodhd_gateway

    monkeypatch.setattr(api, "eodhd_gateway_factory", mock_factory)
    return mock_eodhd_gateway


@pytest.fixture
async def auth_client_with_mock_eodhd(
    mock_eodhd_gateway_factory, test_user: UserSchema, db_session: AsyncSession  # noqa: ARG001
):
    """Create an HTTP test client with auth token and mocked EODHD API."""
    # Create UserApi to generate token
    user_repository = SqlAlchemyUserRepository(session=db_session)
    user_api = UserApi(user_repository=user_repository)

    # Generate access token for test user
    access_token = user_api.create_access_token(test_user.email)

    # Create test client with the real app and authorization header
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {access_token}"},
        ) as client:
            yield client
