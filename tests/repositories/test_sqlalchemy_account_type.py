"""Unit tests for SqlAlchemyAccountTypeRepository."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from src.models import Base
from src.models.account_type import AccountType as AccountTypeModel
from src.repositories.sqlalchemy.sqlalchemy_account_type import (
    SqlAlchemyAccountTypeRepository,
)
from src.schemas.account_type import AccountType


@pytest_asyncio.fixture(scope="function")
async def account_type_test_engine() -> AsyncEngine:
    """Create test database engine for account type repository tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def account_type_db_session(
    account_type_test_engine: AsyncEngine,
) -> AsyncSession:
    """Provide a fresh database session for each test."""
    from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: PLC0415

    async_session = async_sessionmaker(account_type_test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def account_type_repository(
    account_type_db_session: AsyncSession,
) -> SqlAlchemyAccountTypeRepository:
    """Create a repository instance for testing."""
    return SqlAlchemyAccountTypeRepository(session=account_type_db_session)


class TestSqlAlchemyAccountTypeRepository:
    """Test suite for SqlAlchemyAccountTypeRepository."""

    @pytest.mark.asyncio
    async def test_get_account_type_success(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
        account_type_db_session: AsyncSession,
    ) -> None:
        """Test retrieving an account type by ID."""
        # Create account type directly in database
        account_type_model = AccountTypeModel(
            id=1,
            name="TFSA",
            country="CA",
            tax_advantaged=True,
        )
        account_type_db_session.add(account_type_model)
        await account_type_db_session.commit()

        result = await account_type_repository.get_account_type(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "TFSA"
        assert result.country == "CA"
        assert result.tax_advantaged is True
        assert isinstance(result, AccountType)

    @pytest.mark.asyncio
    async def test_get_account_type_not_found(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
    ) -> None:
        """Test retrieving a non-existent account type returns None."""
        result = await account_type_repository.get_account_type(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_account_type_returns_schema(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
        account_type_db_session: AsyncSession,
    ) -> None:
        """Test that repository returns proper AccountType schema."""
        account_type_model = AccountTypeModel(
            id=2,
            name="RRSP",
            country="CA",
            tax_advantaged=True,
        )
        account_type_db_session.add(account_type_model)
        await account_type_db_session.commit()

        result = await account_type_repository.get_account_type(2)

        assert isinstance(result, AccountType)
        assert not isinstance(result, AccountTypeModel)

    @pytest.mark.asyncio
    async def test_get_multiple_account_types(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
        account_type_db_session: AsyncSession,
    ) -> None:
        """Test retrieving multiple different account types."""
        # Create multiple account types
        account_types_data = [
            (1, "TFSA", "CA", True),
            (2, "RRSP", "CA", True),
            (3, "FHSA", "CA", True),
            (4, "Non-Registered", "CA", False),
            (5, "401k", "US", True),
        ]

        for id_, name, country, tax_advantaged in account_types_data:
            account_type_model = AccountTypeModel(
                id=id_,
                name=name,
                country=country,
                tax_advantaged=tax_advantaged,
            )
            account_type_db_session.add(account_type_model)

        await account_type_db_session.commit()

        # Retrieve each and verify
        for id_, name, country, tax_advantaged in account_types_data:
            result = await account_type_repository.get_account_type(id_)
            assert result is not None
            assert result.id == id_
            assert result.name == name
            assert result.country == country
            assert result.tax_advantaged == tax_advantaged

    @pytest.mark.asyncio
    async def test_get_account_type_with_default_country(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
        account_type_db_session: AsyncSession,
    ) -> None:
        """Test that account type defaults to Canada."""
        account_type_model = AccountTypeModel(
            id=10,
            name="Default Country Type",
            country="CA",
            tax_advantaged=False,
        )
        account_type_db_session.add(account_type_model)
        await account_type_db_session.commit()

        result = await account_type_repository.get_account_type(10)

        assert result.country == "CA"

    @pytest.mark.asyncio
    async def test_get_account_type_non_canadian(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
        account_type_db_session: AsyncSession,
    ) -> None:
        """Test retrieving account type from non-Canadian country."""
        account_type_model = AccountTypeModel(
            id=20,
            name="US 401k",
            country="US",
            tax_advantaged=True,
        )
        account_type_db_session.add(account_type_model)
        await account_type_db_session.commit()

        result = await account_type_repository.get_account_type(20)

        assert result is not None
        assert result.country == "US"
        assert result.name == "US 401k"

    @pytest.mark.asyncio
    async def test_get_account_type_tax_advantaged_values(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
        account_type_db_session: AsyncSession,
    ) -> None:
        """Test both tax advantaged and non-tax advantaged account types."""
        # Tax advantaged
        tax_adv = AccountTypeModel(
            id=30,
            name="Tax Advantaged",
            country="CA",
            tax_advantaged=True,
        )

        # Non tax advantaged
        non_tax_adv = AccountTypeModel(
            id=31,
            name="Non Tax Advantaged",
            country="CA",
            tax_advantaged=False,
        )

        account_type_db_session.add_all([tax_adv, non_tax_adv])
        await account_type_db_session.commit()

        tax_adv_result = await account_type_repository.get_account_type(30)
        non_tax_adv_result = await account_type_repository.get_account_type(31)

        assert tax_adv_result.tax_advantaged is True
        assert non_tax_adv_result.tax_advantaged is False

    @pytest.mark.asyncio
    async def test_get_account_type_field_validation(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
        account_type_db_session: AsyncSession,
    ) -> None:
        """Test that all account type fields are properly set and accessible."""
        account_type_model = AccountTypeModel(
            id=40,
            name="Complete Type",
            country="CA",
            tax_advantaged=True,
        )
        account_type_db_session.add(account_type_model)
        await account_type_db_session.commit()

        result = await account_type_repository.get_account_type(40)

        # Verify all fields
        assert hasattr(result, "id")
        assert hasattr(result, "name")
        assert hasattr(result, "country")
        assert hasattr(result, "tax_advantaged")

        assert result.id == 40
        assert isinstance(result.id, int)
        assert isinstance(result.name, str)
        assert isinstance(result.country, str)
        assert isinstance(result.tax_advantaged, bool)

    @pytest.mark.asyncio
    async def test_get_account_type_with_special_characters_in_name(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
        account_type_db_session: AsyncSession,
    ) -> None:
        """Test retrieving account type with special characters in name."""
        special_name = "HSA (Health Savings Account)"
        account_type_model = AccountTypeModel(
            id=50,
            name=special_name,
            country="US",
            tax_advantaged=True,
        )
        account_type_db_session.add(account_type_model)
        await account_type_db_session.commit()

        result = await account_type_repository.get_account_type(50)

        assert result.name == special_name

    @pytest.mark.asyncio
    async def test_get_account_type_with_long_name(
        self,
        account_type_repository: SqlAlchemyAccountTypeRepository,
        account_type_db_session: AsyncSession,
    ) -> None:
        """Test retrieving account type with very long name."""
        long_name = "A" * 200 + " Account Type"
        account_type_model = AccountTypeModel(
            id=60,
            name=long_name,
            country="CA",
            tax_advantaged=False,
        )
        account_type_db_session.add(account_type_model)
        await account_type_db_session.commit()

        result = await account_type_repository.get_account_type(60)

        assert result.name == long_name
