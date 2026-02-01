"""Integration test fixtures using in-memory SQLite database."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4
import os

import bcrypt
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

# Override database URL before importing app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from src.account.api_types import AccountTypeEnum
from src.auth.model import _password_hasher
from src.account.enum import InstitutionEnum
from src.account.model import (
    AccountModel,
    AccountTypeModel,
    InstitutionModel,
    PositionModel,
)
from src.account.schema import AccountSchema, PositionSchema
from src.auth.api import UserApi
from src.auth.model import UserModel
from src.auth.repository_sqlalchemy import SqlAlchemyUserRepository
from src.auth.schema import UserSchema
from src.config.database import BaseModel, sessionmanager
from src.integration.model import IntegrationUserModel
from src.integration.schema import IntegrationUserSchema
from src.main import app
from src.market.model import SecurityModel
from src.market.schema import SecuritySchema


@pytest.fixture
async def auth_client(test_user: UserSchema, db_session: AsyncSession):
    """Create an HTTP test client with auth token for test user."""
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


@pytest.fixture
async def test_account(
    db_session: AsyncSession, test_user: UserSchema
) -> AccountSchema:
    """Create and persist a single test account for the test user."""
    account_model = AccountModel(
        id=uuid4(),
        external_id="ext_id_0",
        name="Test Account",
        user_id=test_user.id,
        account_type_id=AccountTypeEnum.TFSA.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        created_at=datetime.now(UTC),
        deleted_at=None,
    )
    db_session.add(account_model)
    await db_session.commit()
    await db_session.refresh(account_model)

    return AccountSchema(
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


@pytest.fixture
async def test_accounts(
    db_session: AsyncSession, test_user: UserSchema
) -> list[AccountSchema]:
    """Create and persist two test accounts for the test user."""
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
        await db_session.flush()
        await db_session.refresh(account_model)

        accounts.append(
            AccountSchema(
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


@pytest.fixture
async def other_user_account(
    db_session: AsyncSession, other_user: UserSchema
) -> AccountSchema:
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

    return AccountSchema(
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


@pytest.fixture
async def test_security(db_session: AsyncSession) -> SecuritySchema:
    """Create and persist a test security."""
    from src.market.api_types import SecurityId

    security = SecurityModel(
        id=uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        currency="USD",
        name="Apple Inc.",
        isin="US0378331005",
        is_active=True,
    )

    db_session.add(security)
    await db_session.commit()
    await db_session.refresh(security)

    return SecuritySchema(
        id=security.id,
        symbol=security.symbol,
        exchange=security.exchange,
        currency=security.currency,
        name=security.name,
        isin=security.isin,
        is_active=security.is_active,
        updated_at=security.updated_at,
    )


@pytest.fixture
async def test_position(
    db_session: AsyncSession,
    test_account: AccountSchema,
    test_security: SecuritySchema,
) -> PositionSchema:
    """Create and persist a test position."""
    from decimal import Decimal

    position_model = PositionModel(
        id=uuid4(),
        account_id=test_account.id,
        security_id=test_security.id,
        quantity=Decimal("10.0"),
        average_cost=Decimal("150.0"),
    )
    db_session.add(position_model)
    await db_session.commit()
    await db_session.refresh(position_model)

    return PositionSchema(
        id=position_model.id,
        account_id=position_model.account_id,
        security_id=position_model.security_id,
        quantity=position_model.quantity,
        average_cost=position_model.average_cost,
        updated_at=position_model.updated_at,
    )


@pytest.fixture
async def test_positions(
    db_session: AsyncSession,
    test_accounts: list[AccountSchema],
    test_security: SecuritySchema,
) -> list[PositionSchema]:
    """Create and persist test positions for the first test account."""
    from decimal import Decimal

    position_model = PositionModel(
        id=uuid4(),
        account_id=test_accounts[0].id,
        security_id=test_security.id,
        quantity=Decimal("10.0"),
        average_cost=Decimal("150.0"),
    )
    db_session.add(position_model)
    await db_session.commit()
    await db_session.refresh(position_model)

    return [
        PositionSchema(
            id=position_model.id,
            account_id=position_model.account_id,
            security_id=position_model.security_id,
            quantity=position_model.quantity,
            average_cost=position_model.average_cost,
            updated_at=position_model.updated_at,
        )
    ]


@pytest.fixture
async def test_position_for_first_account(
    db_session: AsyncSession,
    test_accounts: list[AccountSchema],
    test_security: SecuritySchema,
) -> PositionSchema:
    """Create and persist a test position for the first test account."""
    from decimal import Decimal

    position_model = PositionModel(
        id=uuid4(),
        account_id=test_accounts[0].id,
        security_id=test_security.id,
        quantity=Decimal("10.0"),
        average_cost=Decimal("150.0"),
    )
    db_session.add(position_model)
    await db_session.commit()
    await db_session.refresh(position_model)

    return PositionSchema(
        id=position_model.id,
        account_id=position_model.account_id,
        security_id=position_model.security_id,
        quantity=position_model.quantity,
        average_cost=position_model.average_cost,
        updated_at=position_model.updated_at,
    )


@pytest.fixture
async def test_integration_user(
    db_session: AsyncSession, test_user: UserSchema
) -> IntegrationUserSchema:
    """Create and persist a test integration user."""
    integration_user_model = IntegrationUserModel(
        id=uuid4(),
        user_id=test_user.id,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        external_user_id="ext_user_123",
        display_name="John Doe",
        last_used_at=datetime.now(UTC),
    )

    db_session.add(integration_user_model)
    await db_session.commit()
    await db_session.refresh(integration_user_model)

    return IntegrationUserSchema(
        id=integration_user_model.id,
        user_id=integration_user_model.user_id,
        institution_id=integration_user_model.institution_id,
        external_user_id=integration_user_model.external_user_id,
        display_name=integration_user_model.display_name,
        last_used_at=integration_user_model.last_used_at,
    )


@pytest.fixture
async def test_external_user(
    db_session: AsyncSession, test_user: UserSchema
) -> IntegrationUserSchema:
    """Create and persist a test external user for the test user."""
    integration_user_model = IntegrationUserModel(
        id=uuid4(),
        user_id=test_user.id,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        external_user_id="ext_user_test",
        display_name="Test External User",
        last_used_at=datetime.now(UTC),
    )

    db_session.add(integration_user_model)
    await db_session.commit()
    await db_session.refresh(integration_user_model)

    return IntegrationUserSchema(
        id=integration_user_model.id,
        user_id=integration_user_model.user_id,
        institution_id=integration_user_model.institution_id,
        external_user_id=integration_user_model.external_user_id,
        display_name=integration_user_model.display_name,
        last_used_at=integration_user_model.last_used_at,
    )


@pytest.fixture
async def other_user_external_user(
    db_session: AsyncSession, other_user: UserSchema
) -> IntegrationUserSchema:
    """Create and persist an external user owned by a different user."""
    integration_user_model = IntegrationUserModel(
        id=uuid4(),
        user_id=other_user.id,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        external_user_id="ext_user_other",
        display_name="Other User External",
        last_used_at=datetime.now(UTC),
    )

    db_session.add(integration_user_model)
    await db_session.commit()
    await db_session.refresh(integration_user_model)

    return IntegrationUserSchema(
        id=integration_user_model.id,
        user_id=integration_user_model.user_id,
        institution_id=integration_user_model.institution_id,
        external_user_id=integration_user_model.external_user_id,
        display_name=integration_user_model.display_name,
        last_used_at=integration_user_model.last_used_at,
    )
