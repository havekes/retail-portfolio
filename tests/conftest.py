"""Integration test fixtures using in-memory SQLite database."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from svcs import Container, Registry

from src.enums import AccountTypeEnum, InstitutionEnum
from src.models import Base
from src.models.account import Account as AccountModel
from src.models.account_type import AccountType as AccountTypeModel
from src.models.external_user import ExternalUser as ExternalUserModel
from src.models.institution import Institution as InstitutionModel
from src.models.position import Position as PositionModel
from src.models.security import Security as SecurityModel
from src.models.user import User as UserModel
from src.repositories.account import AccountRepository
from src.repositories.position import PositionRepository
from src.schemas import User
from src.schemas.account import Account
from src.schemas.external_user import FullExternalUser
from src.schemas.position import Position


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Return in-memory SQLite database URL for testing."""
    return "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine(test_db_url: str) -> AsyncGenerator[AsyncEngine]:
    """Create test database engine."""
    engine = create_async_engine(test_db_url, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables and dispose engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Provide database session for tests."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def services_container(db_session: AsyncSession) -> AsyncGenerator[Container]:
    """Create services container with test database."""
    registry = Registry()

    # Register session factory that returns our test session
    async def test_session_factory():
        yield db_session

    registry.register_factory(AsyncSession, test_session_factory)

    # Register all other services from the main config
    from src.external.api_wrapper import ExternalAPIWrapper
    from src.external.wealthsimple import WealthsimpleApiWrapper
    from src.repositories.account_type import AccountTypeRepository
    from src.repositories.external_user import ExternalUserRepository
    from src.repositories.security import SecurityRepository
    from src.repositories.sqlalchemy.sqlalchemy_account import (
        sqlalchemy_account_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_account_type import (
        sqlalchemy_account_type_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_external_user import (
        sqlalchemy_external_user_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_position import (
        sqlalchemy_position_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_security import (
        sqlaclhemy_security_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_user import (
        sqlalchemy_user_repository_factory,
    )
    from src.repositories.user import UserRepository
    from src.services.auth import AuthService, auth_service_factory
    from src.services.authorization import (
        AuthorizationService,
        authorization_service_factory,
    )
    from src.services.external_user import (
        ExternalUserService,
        external_user_service_factory,
    )
    from src.services.position import PositionService, position_service_factory
    from src.services.user import UserService, user_service_factory

    # Repositories
    registry.register_factory(AccountRepository, sqlalchemy_account_repository_factory)
    registry.register_factory(
        AccountTypeRepository, sqlalchemy_account_type_repository_factory
    )
    registry.register_factory(
        ExternalUserRepository, sqlalchemy_external_user_repository_factory
    )
    registry.register_factory(
        PositionRepository, sqlalchemy_position_repository_factory
    )
    registry.register_factory(UserRepository, sqlalchemy_user_repository_factory)
    registry.register_factory(
        SecurityRepository, sqlaclhemy_security_repository_factory
    )

    # Services
    registry.register_factory(AuthService, auth_service_factory)
    registry.register_factory(AuthorizationService, authorization_service_factory)
    registry.register_factory(ExternalUserService, external_user_service_factory)
    registry.register_factory(PositionService, position_service_factory)
    registry.register_factory(UserService, user_service_factory)

    # Mock external API wrapper factory
    async def mock_external_api_wrapper_factory(
        container: Container,
    ) -> AsyncGenerator[WealthsimpleApiWrapper]:
        """Create a mock external API wrapper for testing."""
        mock_wrapper = MagicMock(spec=WealthsimpleApiWrapper)
        mock_wrapper.login = MagicMock(return_value=True)
        mock_wrapper.list_accounts = AsyncMock(return_value=[])
        mock_wrapper.import_accounts = AsyncMock(return_value=[])
        mock_wrapper.import_positions = AsyncMock(return_value=[])
        yield mock_wrapper

    registry.register_factory(WealthsimpleApiWrapper, mock_external_api_wrapper_factory)

    container = Container(registry)
    yield container
    await container.aclose()


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, seed_reference_data: None) -> User:
    """Create and persist a test user."""
    import bcrypt

    user_id = uuid4()
    # Hash a test password for login
    test_password = "testpass"
    hashed_password = bcrypt.hashpw(
        test_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    user_model = UserModel(
        id=user_id,
        email="test@example.com",
        password=hashed_password,
        is_active=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )

    db_session.add(user_model)
    await db_session.commit()
    await db_session.refresh(user_model)

    return User(
        id=user_model.id,
        email=user_model.email,
        password=user_model.password,
        is_active=user_model.is_active,
        last_login_at=user_model.last_login_at,
        created_at=user_model.created_at,
    )


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession, seed_reference_data: None) -> User:
    """Create and persist another user for testing authorization."""
    user_id = uuid4()
    user_model = UserModel(
        id=user_id,
        email="other@example.com",
        password="hashed_password",
        is_active=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )

    db_session.add(user_model)
    await db_session.commit()
    await db_session.refresh(user_model)

    return User(
        id=user_model.id,
        email=user_model.email,
        password=user_model.password,
        is_active=user_model.is_active,
        last_login_at=user_model.last_login_at,
        created_at=user_model.created_at,
    )


@pytest_asyncio.fixture
async def test_accounts(db_session: AsyncSession, test_user: User) -> list[Account]:
    """Create and persist test accounts for the test user."""
    accounts = []
    for i in range(2):
        account_model = AccountModel(
            id=uuid4(),
            external_id=f"ext_id_{i}",
            name=f"Test Account {i}",
            user_id=test_user.id,
            account_type_id=AccountTypeEnum.TFSA.value,
            institution_id=InstitutionEnum.WEALTHSIMPLE.value,
            currency="CAD",
            is_active=True,
            created_at=datetime.now(UTC),
            deleted_at=None,
        )
        db_session.add(account_model)
        accounts.append(
            Account(
                id=account_model.id,
                external_id=account_model.external_id,
                name=account_model.name,
                user_id=account_model.user_id,
                account_type_id=account_model.account_type_id,
                institution_id=account_model.institution_id,
                currency=account_model.currency,
                is_active=account_model.is_active,
                created_at=account_model.created_at,
                deleted_at=account_model.deleted_at,
            )
        )

    await db_session.commit()
    return accounts


@pytest_asyncio.fixture
async def other_user_account(db_session: AsyncSession, other_user: User) -> Account:
    """Create and persist an account owned by a different user."""
    account_model = AccountModel(
        id=uuid4(),
        external_id="other_ext_id",
        name="Other Account",
        user_id=other_user.id,
        account_type_id=AccountTypeEnum.RRSP.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        created_at=datetime.now(UTC),
        deleted_at=None,
    )

    db_session.add(account_model)
    await db_session.commit()
    await db_session.refresh(account_model)

    return Account(
        id=account_model.id,
        external_id=account_model.external_id,
        name=account_model.name,
        user_id=account_model.user_id,
        account_type_id=account_model.account_type_id,
        institution_id=account_model.institution_id,
        currency=account_model.currency,
        is_active=account_model.is_active,
        created_at=account_model.created_at,
        deleted_at=account_model.deleted_at,
    )


@pytest_asyncio.fixture
async def test_security(db_session: AsyncSession) -> SecurityModel:
    """Create and persist a test security."""
    security = SecurityModel(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        market_cap=3000000000000,
        pe_ratio=25.5,
        is_active=True,
    )

    db_session.add(security)
    await db_session.commit()
    await db_session.refresh(security)
    return security


@pytest_asyncio.fixture
async def test_positions(
    db_session: AsyncSession,
    test_accounts: list[Account],
    test_security: SecurityModel,
) -> list[Position]:
    """Create and persist test positions."""
    account = test_accounts[0]
    positions = []

    position_model = PositionModel(
        id=uuid4(),
        account_id=account.id,
        security_symbol=test_security.symbol,
        quantity=10.0,
        average_cost=150.0,
        updated_at=datetime.now(UTC),
    )
    db_session.add(position_model)

    await db_session.commit()
    await db_session.refresh(position_model)

    positions.append(
        Position(
            id=position_model.id,
            account_id=position_model.account_id,
            security_symbol=position_model.security_symbol,
            quantity=position_model.quantity,
            average_cost=position_model.average_cost,
            updated_at=position_model.updated_at,
        )
    )

    return positions


@pytest_asyncio.fixture
async def test_external_user(
    db_session: AsyncSession, test_user: User
) -> FullExternalUser:
    """Create and persist a test external user."""
    external_user_model = ExternalUserModel(
        id=uuid4(),
        user_id=test_user.id,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        external_user_id="ext_user_123",
        display_name="John Doe",
        last_used_at=datetime.now(UTC),
    )

    db_session.add(external_user_model)
    await db_session.commit()
    await db_session.refresh(external_user_model)

    return FullExternalUser(
        id=external_user_model.id,
        user_id=external_user_model.user_id,
        institution_id=external_user_model.institution_id,
        external_user_id=external_user_model.external_user_id,
        display_name=external_user_model.display_name,
        last_used_at=external_user_model.last_used_at,
    )


@pytest_asyncio.fixture
async def other_user_external_user(
    db_session: AsyncSession, other_user: User
) -> FullExternalUser:
    """Create and persist an external user for the other user."""
    external_user_model = ExternalUserModel(
        id=uuid4(),
        user_id=other_user.id,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        external_user_id="ext_user_456",
        display_name="Jane Smith",
        last_used_at=datetime.now(UTC),
    )

    db_session.add(external_user_model)
    await db_session.commit()
    await db_session.refresh(external_user_model)

    return FullExternalUser(
        id=external_user_model.id,
        user_id=external_user_model.user_id,
        institution_id=external_user_model.institution_id,
        external_user_id=external_user_model.external_user_id,
        display_name=external_user_model.display_name,
        last_used_at=external_user_model.last_used_at,
    )


@pytest_asyncio.fixture
async def test_registry(services_container: Container) -> AsyncGenerator[Registry]:
    """Create a test registry with test services."""
    # Extract the registry from the test services container
    # The registry is already populated by services_container fixture
    registry = Registry()

    # Register the test session factory that returns our test database session
    from sqlalchemy.ext.asyncio import AsyncSession

    async def test_session_factory():
        # Get session from services_container which uses test database
        return await services_container.aget(AsyncSession)

    registry.register_factory(AsyncSession, test_session_factory)

    # Register all other services using register_factory from services_container
    # by re-registering them
    from src.repositories.account import AccountRepository
    from src.repositories.account_type import AccountTypeRepository
    from src.repositories.external_user import ExternalUserRepository
    from src.repositories.position import PositionRepository
    from src.repositories.security import SecurityRepository
    from src.repositories.user import UserRepository
    from src.repositories.sqlalchemy.sqlalchemy_account import (
        sqlalchemy_account_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_account_type import (
        sqlalchemy_account_type_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_external_user import (
        sqlalchemy_external_user_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_position import (
        sqlalchemy_position_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_security import (
        sqlaclhemy_security_repository_factory,
    )
    from src.repositories.sqlalchemy.sqlalchemy_user import (
        sqlalchemy_user_repository_factory,
    )
    from src.services.auth import AuthService, auth_service_factory
    from src.services.authorization import (
        AuthorizationService,
        authorization_service_factory,
    )
    from src.services.external_user import (
        ExternalUserService,
        external_user_service_factory,
    )
    from src.services.position import PositionService, position_service_factory
    from src.services.user import UserService, user_service_factory

    # Repositories
    registry.register_factory(AccountRepository, sqlalchemy_account_repository_factory)
    registry.register_factory(
        AccountTypeRepository, sqlalchemy_account_type_repository_factory
    )
    registry.register_factory(
        ExternalUserRepository, sqlalchemy_external_user_repository_factory
    )
    registry.register_factory(
        PositionRepository, sqlalchemy_position_repository_factory
    )
    registry.register_factory(UserRepository, sqlalchemy_user_repository_factory)
    registry.register_factory(
        SecurityRepository, sqlaclhemy_security_repository_factory
    )

    # Services
    registry.register_factory(AuthService, auth_service_factory)
    registry.register_factory(AuthorizationService, authorization_service_factory)
    registry.register_factory(ExternalUserService, external_user_service_factory)
    registry.register_factory(PositionService, position_service_factory)
    registry.register_factory(UserService, user_service_factory)

    # Mock external API wrapper
    from unittest.mock import AsyncMock, MagicMock
    from src.external.wealthsimple import WealthsimpleApiWrapper

    async def mock_external_api_wrapper_factory(
        container: Container,
    ) -> AsyncGenerator[WealthsimpleApiWrapper]:
        """Create a mock external API wrapper for testing."""
        mock_wrapper = MagicMock(spec=WealthsimpleApiWrapper)
        mock_wrapper.login = MagicMock(return_value=True)
        mock_wrapper.list_accounts = AsyncMock(return_value=[])
        mock_wrapper.import_accounts = AsyncMock(return_value=[])
        mock_wrapper.import_positions = AsyncMock(return_value=[])
        yield mock_wrapper

    registry.register_factory(WealthsimpleApiWrapper, mock_external_api_wrapper_factory)

    yield registry


@pytest.fixture
def auth_client(test_registry: Registry, test_user: User):
    """Create an HTTP test client with auth token for test user."""
    import asyncio

    import svcs
    from fastapi import FastAPI
    from fastapi.middleware import Middleware
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.testclient import TestClient
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    from src.config.settings import settings
    from src.routers import init_routers
    from src.services.auth import AuthService

    # Create access token for test user
    auth_service = asyncio.run(
        svcs.Container(test_registry).aget(AuthService)
    )
    access_token = auth_service.create_access_token(test_user.email)

    # Middleware that injects the test registry into request state
    # This is necessary because svcs.fastapi.container expects the registry
    # to be available in request.state.svcs_registry, which is normally set
    # by the svcs lifespan decorator
    class SVCSTestMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.svcs_registry = test_registry
            response = await call_next(request)
            return response

    # Create test app with middleware to inject registry
    test_app = FastAPI(
        middleware=[
            Middleware(SVCSTestMiddleware),
            Middleware(
                CORSMiddleware,
                allow_origins=[origin.strip() for origin in settings.cors_allow_origins.split(",")],
                allow_credentials=True,
                allow_methods=[origin.strip() for origin in settings.cors_allow_methods.split(",")],
                allow_headers=[origin.strip() for origin in settings.cors_allow_headers.split(",")],
            ),
        ]
    )

    # Initialize routers
    init_routers(test_app)

    # Create test client
    client = TestClient(test_app)

    # Add authorization header to all requests
    client.headers.update({"Authorization": f"Bearer {access_token}"})

    yield client
