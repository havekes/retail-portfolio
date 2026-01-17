"""Unit tests for SqlAlchemySecurityRepository."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from src.models import Base
from src.models.security import Security as SecurityModel
from src.repositories.sqlalchemy.sqlalchemy_security import (
    SqlAlchemySecurityRepository,
)
from src.schemas.security import Security


@pytest_asyncio.fixture(scope="function")
async def security_test_engine() -> AsyncEngine:
    """Create test database engine for security repository tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def security_db_session(security_test_engine: AsyncEngine) -> AsyncSession:
    """Provide a fresh database session for each test."""
    from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: PLC0415

    async_session = async_sessionmaker(security_test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def security_repository(
    security_db_session: AsyncSession,
) -> SqlAlchemySecurityRepository:
    """Create a repository instance for testing."""
    return SqlAlchemySecurityRepository(session=security_db_session)


class TestSqlAlchemySecurityRepository:
    """Test suite for SqlAlchemySecurityRepository."""

    @pytest.mark.asyncio
    async def test_get_or_create_new_security(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test creating a new security when it doesn't exist."""
        security_schema = Security(
            symbol="AAPL",
            name="Apple Inc.",
            market_cap=3000000000000.0,
            sector="Technology",
            industry="Consumer Electronics",
            pe_ratio=25.5,
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."
        assert result.market_cap == 3000000000000.0
        assert result.sector == "Technology"
        assert result.industry == "Consumer Electronics"
        assert result.pe_ratio == 25.5
        assert result.is_active is True
        assert isinstance(result, Security)

        # Verify persistence
        persisted = await security_db_session.get(SecurityModel, "AAPL")
        assert persisted is not None
        assert persisted.name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_get_or_create_existing_security(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test retrieving existing security returns it unchanged."""
        # Create security directly in database
        security_model = SecurityModel(
            symbol="GOOGL",
            name="Alphabet Inc.",
            market_cap=1800000000000.0,
            sector="Technology",
            industry="Internet Services",
            pe_ratio=22.3,
            is_active=True,
        )
        security_db_session.add(security_model)
        await security_db_session.commit()

        # Try to create same security with different details
        security_schema = Security(
            symbol="GOOGL",
            name="Google (New Name)",  # Different name
            market_cap=1900000000000.0,  # Different market cap
            sector="Tech",  # Different sector
            industry="Search",  # Different industry
            pe_ratio=23.0,  # Different PE ratio
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        # Should return existing security, not the new details
        assert result.symbol == "GOOGL"
        assert result.name == "Alphabet Inc."  # Original name preserved
        assert result.market_cap == 1800000000000.0  # Original market cap

    @pytest.mark.asyncio
    async def test_get_or_create_multiple_securities(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test creating multiple different securities."""
        securities_data = [
            Security(
                symbol="MSFT",
                name="Microsoft Corporation",
                market_cap=2700000000000.0,
                sector="Technology",
                industry="Software",
                pe_ratio=28.5,
                is_active=True,
            ),
            Security(
                symbol="AMZN",
                name="Amazon Inc.",
                market_cap=1600000000000.0,
                sector="Consumer Cyclical",
                industry="Retail",
                pe_ratio=50.2,
                is_active=True,
            ),
            Security(
                symbol="TSLA",
                name="Tesla Inc.",
                market_cap=800000000000.0,
                sector="Consumer Cyclical",
                industry="Automotive",
                pe_ratio=35.0,
                is_active=True,
            ),
        ]

        results = []
        for security_data in securities_data:
            result = await security_repository.get_or_create(security_data)
            results.append(result)

        assert len(results) == 3
        assert all(isinstance(s, Security) for s in results)
        assert {s.symbol for s in results} == {"MSFT", "AMZN", "TSLA"}

    @pytest.mark.asyncio
    async def test_get_or_create_security_without_optional_fields(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test creating security without optional fields (sector, industry, pe_ratio)."""
        security_schema = Security(
            symbol="BRK",
            name="Berkshire Hathaway",
            market_cap=700000000000.0,
            sector=None,
            industry=None,
            pe_ratio=None,
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        assert result.symbol == "BRK"
        assert result.name == "Berkshire Hathaway"
        assert result.sector is None
        assert result.industry is None
        assert result.pe_ratio is None

    @pytest.mark.asyncio
    async def test_get_or_create_security_inactive(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test creating an inactive security."""
        security_schema = Security(
            symbol="DELISTED",
            name="Delisted Company",
            market_cap=0.0,
            sector="N/A",
            industry="N/A",
            pe_ratio=None,
            is_active=False,
        )

        result = await security_repository.get_or_create(security_schema)

        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_get_or_create_returns_schema(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test that repository returns Security schema, not model."""
        security_schema = Security(
            symbol="SCHEMA",
            name="Schema Test",
            market_cap=100000000.0,
            sector="Test",
            industry="Testing",
            pe_ratio=10.0,
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        assert isinstance(result, Security)
        assert not isinstance(result, SecurityModel)

    @pytest.mark.asyncio
    async def test_get_or_create_preserves_all_fields(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test that all fields are preserved when creating security."""
        security_schema = Security(
            symbol="COMPLETE",
            name="Complete Security Info",
            market_cap=5000000000.0,
            sector="Healthcare",
            industry="Pharmaceuticals",
            pe_ratio=18.75,
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        # Verify all fields
        assert result.symbol == "COMPLETE"
        assert result.name == "Complete Security Info"
        assert result.market_cap == 5000000000.0
        assert result.sector == "Healthcare"
        assert result.industry == "Pharmaceuticals"
        assert result.pe_ratio == 18.75
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_get_or_create_with_large_market_cap(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test creating security with very large market cap."""
        large_cap = 99999999999999.99
        security_schema = Security(
            symbol="MEGA",
            name="Mega Cap Company",
            market_cap=large_cap,
            sector="Mega",
            industry="Mega Cap",
            pe_ratio=100.0,
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        assert result.market_cap == large_cap

    @pytest.mark.asyncio
    async def test_get_or_create_with_small_market_cap(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test creating security with very small market cap."""
        small_cap = 0.01
        security_schema = Security(
            symbol="MICRO",
            name="Micro Cap Company",
            market_cap=small_cap,
            sector="Micro",
            industry="Micro Cap",
            pe_ratio=5.0,
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        assert result.market_cap == small_cap

    @pytest.mark.asyncio
    async def test_get_or_create_with_special_characters_in_name(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test creating security with special characters in name."""
        special_name = "Company & Co. (NYSE: XYZ)"
        security_schema = Security(
            symbol="SPEC",
            name=special_name,
            market_cap=500000000.0,
            sector="Special",
            industry="Special",
            pe_ratio=15.0,
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        assert result.name == special_name

    @pytest.mark.asyncio
    async def test_get_or_create_with_zero_pe_ratio(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test creating security with zero PE ratio."""
        security_schema = Security(
            symbol="ZERO",
            name="No Earnings Company",
            market_cap=100000000.0,
            sector="Unprofitable",
            industry="Unprofitable",
            pe_ratio=0.0,
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        assert result.pe_ratio == 0.0

    @pytest.mark.asyncio
    async def test_get_or_create_case_sensitive_symbol(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test that symbols are case-sensitive."""
        security1 = Security(
            symbol="ABC",
            name="ABC Company",
            market_cap=100000000.0,
            sector="Test",
            industry="Test",
            pe_ratio=10.0,
            is_active=True,
        )

        result1 = await security_repository.get_or_create(security1)
        assert result1.symbol == "ABC"

        # Try to create with lowercase - should create new record
        security2 = Security(
            symbol="abc",
            name="abc company",
            market_cap=200000000.0,
            sector="Test",
            industry="Test",
            pe_ratio=12.0,
            is_active=True,
        )

        result2 = await security_repository.get_or_create(security2)
        assert result2.symbol == "abc"

        # Both should exist as separate records
        persisted_abc = await security_db_session.get(SecurityModel, "ABC")
        persisted_abc_lower = await security_db_session.get(SecurityModel, "abc")

        assert persisted_abc is not None
        assert persisted_abc_lower is not None
        assert persisted_abc.name == "ABC Company"
        assert persisted_abc_lower.name == "abc company"

    @pytest.mark.asyncio
    async def test_get_or_create_with_long_names(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test creating security with very long name and sector/industry."""
        long_name = "A" * 200 + " Inc."
        long_sector = "B" * 100
        long_industry = "C" * 100

        security_schema = Security(
            symbol="LONG",
            name=long_name,
            market_cap=1000000000.0,
            sector=long_sector,
            industry=long_industry,
            pe_ratio=20.0,
            is_active=True,
        )

        result = await security_repository.get_or_create(security_schema)

        assert result.name == long_name
        assert result.sector == long_sector
        assert result.industry == long_industry

    @pytest.mark.asyncio
    async def test_get_or_create_idempotent(
        self,
        security_repository: SqlAlchemySecurityRepository,
        security_db_session: AsyncSession,
    ) -> None:
        """Test that calling get_or_create multiple times with same symbol is idempotent."""
        security_schema = Security(
            symbol="IDEM",
            name="Idempotent Test",
            market_cap=500000000.0,
            sector="Test",
            industry="Test",
            pe_ratio=15.0,
            is_active=True,
        )

        result1 = await security_repository.get_or_create(security_schema)
        result2 = await security_repository.get_or_create(security_schema)
        result3 = await security_repository.get_or_create(security_schema)

        assert result1.symbol == result2.symbol == result3.symbol == "IDEM"
        assert result1.name == result2.name == result3.name

        # Verify only one record exists
        count = await security_db_session.execute(
            __import__("sqlalchemy")
            .select(__import__("sqlalchemy").func.count())
            .select_from(SecurityModel)
            .where(SecurityModel.symbol == "IDEM")
        )
        assert count.scalar() == 1
