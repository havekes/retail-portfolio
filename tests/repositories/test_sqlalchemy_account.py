"""Unit tests for SqlAlchemyAccountRepository."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from src.models import Base
from src.models.account import Account as AccountModel
from src.models.account_type import AccountType as AccountTypeModel
from src.models.institution import Institution as InstitutionModel
from src.models.user import User as UserModel
from src.repositories.sqlalchemy.sqlalchemy_account import (
    SqlAlchemyAccountRepository,
)
from src.schemas.account import Account


@pytest_asyncio.fixture(scope="function")
async def account_test_engine() -> AsyncEngine:
    """Create test database engine for account repository tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def account_db_session(account_test_engine: AsyncEngine) -> AsyncSession:
    """Provide a fresh database session for each test."""
    from sqlalchemy.ext.asyncio import (  # noqa: PLC0415
        async_sessionmaker,
    )

    async_session = async_sessionmaker(account_test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def account_repository(
    account_db_session: AsyncSession,
) -> SqlAlchemyAccountRepository:
    """Create a repository instance for testing."""
    return SqlAlchemyAccountRepository(session=account_db_session)


@pytest_asyncio.fixture(scope="function")
async def seed_account_data(account_db_session: AsyncSession) -> tuple:
    """Seed necessary reference data for account tests."""
    # Create user
    user = UserModel(
        id=uuid4(),
        email="test@example.com",
        password="hashed_password",
        is_active=True,
        created_at=datetime.now(UTC),
    )
    account_db_session.add(user)

    # Create account type
    account_type = AccountTypeModel(
        id=1,
        name="TFSA",
        country="CA",
        tax_advantaged=True,
    )
    account_db_session.add(account_type)

    # Create institution
    institution = InstitutionModel(
        id=1,
        name="Wealthsimple",
        country="CA",
        is_active=True,
    )
    account_db_session.add(institution)

    await account_db_session.commit()
    await account_db_session.refresh(user)
    await account_db_session.refresh(account_type)
    await account_db_session.refresh(institution)

    return (user, account_type, institution)


class TestSqlAlchemyAccountRepository:
    """Test suite for SqlAlchemyAccountRepository."""

    @pytest.mark.asyncio
    async def test_create_account_success(
        self,
        account_repository: SqlAlchemyAccountRepository,
        account_db_session: AsyncSession,
        seed_account_data: tuple,
    ) -> None:
        """Test creating a new account successfully."""
        user, account_type, institution = seed_account_data
        account_id = uuid4()

        account_schema = Account(
            id=account_id,
            external_id="ext_123",
            name="My TFSA",
            user_id=user.id,
            account_type_id=account_type.id,
            institution_id=institution.id,
            currency="CAD",
            is_active=True,
            created_at=datetime.now(UTC),
            deleted_at=None,
        )

        result = await account_repository.create_account(account_schema)

        assert result.id == account_id
        assert result.external_id == "ext_123"
        assert result.name == "My TFSA"
        assert result.user_id == user.id
        assert result.is_active is True

        # Verify it was persisted in the database
        persisted = await account_db_session.get(AccountModel, account_id)
        assert persisted is not None
        assert persisted.name == "My TFSA"

    @pytest.mark.asyncio
    async def test_get_account_success(
        self,
        account_repository: SqlAlchemyAccountRepository,
        account_db_session: AsyncSession,
        seed_account_data: tuple,
    ) -> None:
        """Test retrieving an account by ID."""
        user, account_type, institution = seed_account_data
        account_id = uuid4()

        # Create account directly in database
        account_model = AccountModel(
            id=account_id,
            external_id="ext_456",
            name="Test Account",
            user_id=user.id,
            account_type_id=account_type.id,
            institution_id=institution.id,
            currency="USD",
            is_active=True,
            created_at=datetime.now(UTC),
        )
        account_db_session.add(account_model)
        await account_db_session.commit()

        result = await account_repository.get(account_id)

        assert result is not None
        assert result.id == account_id
        assert result.external_id == "ext_456"
        assert result.name == "Test Account"
        assert result.currency == "USD"
        assert isinstance(result, Account)

    @pytest.mark.asyncio
    async def test_get_account_not_found(
        self, account_repository: SqlAlchemyAccountRepository
    ) -> None:
        """Test retrieving a non-existent account returns None."""
        non_existent_id = uuid4()

        result = await account_repository.get(non_existent_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_user_returns_all_accounts(
        self,
        account_repository: SqlAlchemyAccountRepository,
        account_db_session: AsyncSession,
        seed_account_data: tuple,
    ) -> None:
        """Test retrieving all accounts for a user."""
        user, account_type, institution = seed_account_data

        # Create multiple accounts for the same user
        for i in range(3):
            account = AccountModel(
                id=uuid4(),
                external_id=f"ext_{i}",
                name=f"Account {i}",
                user_id=user.id,
                account_type_id=account_type.id,
                institution_id=institution.id,
                currency="CAD",
                is_active=True,
                created_at=datetime.now(UTC),
            )
            account_db_session.add(account)

        await account_db_session.commit()

        result = await account_repository.get_by_user(user.id)

        assert len(result) == 3
        assert all(isinstance(acc, Account) for acc in result)
        assert all(acc.user_id == user.id for acc in result)
        assert {acc.name for acc in result} == {"Account 0", "Account 1", "Account 2"}

    @pytest.mark.asyncio
    async def test_get_by_user_empty_result(
        self, account_repository: SqlAlchemyAccountRepository, seed_account_data: tuple
    ) -> None:
        """Test retrieving accounts for a user with no accounts."""
        user_with_no_accounts_id = uuid4()

        result = await account_repository.get_by_user(user_with_no_accounts_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_exists_by_user_and_external_id_true(
        self,
        account_repository: SqlAlchemyAccountRepository,
        account_db_session: AsyncSession,
        seed_account_data: tuple,
    ) -> None:
        """Test checking if account exists by user and external ID - exists."""
        user, account_type, institution = seed_account_data

        account = AccountModel(
            id=uuid4(),
            external_id="ext_789",
            name="Existing Account",
            user_id=user.id,
            account_type_id=account_type.id,
            institution_id=institution.id,
            currency="CAD",
            is_active=True,
            created_at=datetime.now(UTC),
        )
        account_db_session.add(account)
        await account_db_session.commit()

        result = await account_repository.exists_by_user_and_external_id(
            user.id, "ext_789"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_by_user_and_external_id_false(
        self, account_repository: SqlAlchemyAccountRepository, seed_account_data: tuple
    ) -> None:
        """Test checking if account exists by user and external ID - does not exist."""
        user, _, _ = seed_account_data

        result = await account_repository.exists_by_user_and_external_id(
            user.id, "non_existent_ext_id"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_by_user_and_external_id_different_user(
        self,
        account_repository: SqlAlchemyAccountRepository,
        account_db_session: AsyncSession,
        seed_account_data: tuple,
    ) -> None:
        """Test checking if account exists for different user with same external ID."""
        user1, account_type, institution = seed_account_data

        # Create another user
        user2 = UserModel(
            id=uuid4(),
            email="other@example.com",
            password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
        )
        account_db_session.add(user2)
        await account_db_session.commit()

        # Create account for user1
        account = AccountModel(
            id=uuid4(),
            external_id="shared_ext_id",
            name="Account",
            user_id=user1.id,
            account_type_id=account_type.id,
            institution_id=institution.id,
            currency="CAD",
            is_active=True,
            created_at=datetime.now(UTC),
        )
        account_db_session.add(account)
        await account_db_session.commit()

        # Check that user1 has it but user2 does not
        user1_has_account = await account_repository.exists_by_user_and_external_id(
            user1.id, "shared_ext_id"
        )
        user2_has_account = await account_repository.exists_by_user_and_external_id(
            user2.id, "shared_ext_id"
        )

        assert user1_has_account is True
        assert user2_has_account is False

    @pytest.mark.asyncio
    async def test_rename_account_success(
        self,
        account_repository: SqlAlchemyAccountRepository,
        account_db_session: AsyncSession,
        seed_account_data: tuple,
    ) -> None:
        """Test renaming an account."""
        user, account_type, institution = seed_account_data
        account_id = uuid4()

        # Create account
        account = AccountModel(
            id=account_id,
            external_id="ext_rename",
            name="Original Name",
            user_id=user.id,
            account_type_id=account_type.id,
            institution_id=institution.id,
            currency="CAD",
            is_active=True,
            created_at=datetime.now(UTC),
        )
        account_db_session.add(account)
        await account_db_session.commit()

        result = await account_repository.rename(account_id, "New Name")

        assert result.id == account_id
        assert result.name == "New Name"

        # Verify persistence
        persisted = await account_db_session.get(AccountModel, account_id)
        assert persisted.name == "New Name"

    @pytest.mark.asyncio
    async def test_rename_account_not_found(
        self, account_repository: SqlAlchemyAccountRepository
    ) -> None:
        """Test renaming a non-existent account raises ValueError."""
        non_existent_id = uuid4()

        with pytest.raises(ValueError, match="not found"):
            await account_repository.rename(non_existent_id, "New Name")

    @pytest.mark.asyncio
    async def test_rename_account_multiple_times(
        self,
        account_repository: SqlAlchemyAccountRepository,
        account_db_session: AsyncSession,
        seed_account_data: tuple,
    ) -> None:
        """Test renaming an account multiple times."""
        user, account_type, institution = seed_account_data
        account_id = uuid4()

        account = AccountModel(
            id=account_id,
            external_id="ext_multi",
            name="Name 1",
            user_id=user.id,
            account_type_id=account_type.id,
            institution_id=institution.id,
            currency="CAD",
            is_active=True,
            created_at=datetime.now(UTC),
        )
        account_db_session.add(account)
        await account_db_session.commit()

        # Rename multiple times
        result1 = await account_repository.rename(account_id, "Name 2")
        assert result1.name == "Name 2"

        result2 = await account_repository.rename(account_id, "Name 3")
        assert result2.name == "Name 3"

        result3 = await account_repository.rename(account_id, "Final Name")
        assert result3.name == "Final Name"

    @pytest.mark.asyncio
    async def test_account_schema_validation(
        self,
        account_repository: SqlAlchemyAccountRepository,
        account_db_session: AsyncSession,
        seed_account_data: tuple,
    ) -> None:
        """Test that repository returns proper Account schema."""
        user, account_type, institution = seed_account_data
        account_id = uuid4()

        account_model = AccountModel(
            id=account_id,
            external_id="ext_schema",
            name="Schema Test",
            user_id=user.id,
            account_type_id=account_type.id,
            institution_id=institution.id,
            currency="EUR",
            is_active=False,
            created_at=datetime.now(UTC),
            deleted_at=datetime.now(UTC),
        )
        account_db_session.add(account_model)
        await account_db_session.commit()

        result = await account_repository.get(account_id)

        # Verify schema fields
        assert isinstance(result, Account)
        assert result.id == account_id
        assert result.external_id == "ext_schema"
        assert result.name == "Schema Test"
        assert result.user_id == user.id
        assert result.account_type_id == account_type.id
        assert result.institution_id == institution.id
        assert result.currency == "EUR"
        assert result.is_active is False
        assert result.created_at is not None
        assert result.deleted_at is not None
