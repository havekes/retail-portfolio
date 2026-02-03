"""Authentication and user fixtures."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.api import UserApi
from src.auth.model import _password_hasher
from src.auth.model import UserModel
from src.auth.repository_sqlalchemy import SqlAlchemyUserRepository
from src.auth.schema import UserSchema
from src.main import app
from src.market import api, repository_eodhd
from src.market.api_types import EodhdSearchResult, HistoricalPrice
from src.market.schema import SecuritySchema


class MockEodhdGateway:
    """Mock implementation of EodhdGateway for testing."""

    def search(self, query: str) -> list[EodhdSearchResult]:  # noqa: ARG002
        """Return a mock search result."""
        return [
            {
                "Code": "AAPL",
                "Currency": "USD",
                "Exchange": "US",
                "Name": "Apple Inc",
                "Type": "Common Stock",
                "Country": "USA",
                "ISIN": "US0378331005",
                "isPrimary": "true",
                "previousClose": "170.00",
                "previousCloseDate": "2024-01-01",
            }
        ]

    def get_price_on_date(
        self, security: SecuritySchema, date: date  # noqa: ARG002
    ) -> HistoricalPrice | None:
        """Return a mock price result."""
        return HistoricalPrice(
            security_id=security.id,
            date=date,
            open=Decimal("150.0"),
            high=Decimal("155.0"),
            low=Decimal("149.0"),
            close=Decimal("154.0"),
            adjusted_close=Decimal("153.5"),
            volume=1000000,
        )

    def get_prices(
        self, security: SecuritySchema, from_date: date, to_date: date  # noqa: ARG002
    ) -> list[HistoricalPrice]:
        """Return a mock price list."""
        return [
            HistoricalPrice(
                security_id=security.id,
                date=from_date,
                open=Decimal("150.0"),
                high=Decimal("155.0"),
                low=Decimal("149.0"),
                close=Decimal("154.0"),
                adjusted_close=Decimal("153.5"),
                volume=1000000,
            )
        ]


@pytest.fixture
def mock_eodhd_gateway() -> MockEodhdGateway:
    """Provide a mock EODHD gateway that returns mock payloads."""
    return MockEodhdGateway()


@pytest.fixture
async def auth_client(
    mock_eodhd_gateway: MockEodhdGateway,
    test_user: UserSchema,
    db_session: AsyncSession,
    monkeypatch,
):
    """Create an HTTP test client with auth token and mocked EODHD API."""
    # Create UserApi to generate token
    user_repository = SqlAlchemyUserRepository(session=db_session)
    user_api = UserApi(user_repository=user_repository)

    # Generate access token for test user
    access_token = user_api.create_access_token(test_user.email)

    # Patch the EODHD gateway factory to return the mock gateway
    # (These imports are already at the top of the file)
    # from src.market import api, repository_eodhd

    monkeypatch.setattr(api, "eodhd_gateway_factory", lambda: mock_eodhd_gateway)
    monkeypatch.setattr(
        repository_eodhd, "eodhd_gateway_factory", lambda: mock_eodhd_gateway
    )

    # Create test client with the real app and authorization header
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {access_token}"},
        ) as client:
            yield client


@pytest.fixture
async def test_user(db_session: AsyncSession, seed_reference_data: None) -> UserSchema:  # noqa: ARG001
    """Create and persist a test user."""
    user_id = uuid4()
    # Hash a test password for login (using Argon2 like the repository does)
    test_password = "testpass"  # noqa: S105
    hashed_password = _password_hasher.hash(test_password)

    user_model = UserModel(
        id=user_id,
        email="test@example.com",
        _password_hash=hashed_password,
        is_active=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )

    db_session.add(user_model)
    await db_session.commit()
    await db_session.refresh(user_model)

    return UserSchema(
        id=user_model.id,
        email=user_model.email,
        password=user_model.password,
        is_active=user_model.is_active,
        last_login_at=user_model.last_login_at,
        created_at=user_model.created_at,
    )


@pytest.fixture
async def other_user(
    db_session: AsyncSession,
    seed_reference_data: None,  # noqa: ARG001
) -> UserSchema:
    """Create and persist another user for testing authorization."""

    user_id = uuid4()
    hashed_password = _password_hasher.hash("otherpass")

    user_model = UserModel(
        id=user_id,
        email="other@example.com",
        _password_hash=hashed_password,
        is_active=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )

    db_session.add(user_model)
    await db_session.commit()
    await db_session.refresh(user_model)

    return UserSchema(
        id=user_model.id,
        email=user_model.email,
        password=user_model.password,
        is_active=user_model.is_active,
        last_login_at=user_model.last_login_at,
        created_at=user_model.created_at,
    )