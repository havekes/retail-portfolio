"""Unit tests for SqlAlchemyUserRepository."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from src.models import Base
from src.models.user import User as UserModel
from src.repositories.sqlalchemy.sqlalchemy_user import SqlAlchemyUserRepository
from src.schemas.user import User


@pytest_asyncio.fixture(scope="function")
async def user_test_engine() -> AsyncEngine:
    """Create test database engine for user repository tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def user_db_session(user_test_engine: AsyncEngine) -> AsyncSession:
    """Provide a fresh database session for each test."""
    from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: PLC0415

    async_session = async_sessionmaker(user_test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def user_repository(user_db_session: AsyncSession) -> SqlAlchemyUserRepository:
    """Create a repository instance for testing."""
    return SqlAlchemyUserRepository(session=user_db_session)


class TestSqlAlchemyUserRepository:
    """Test suite for SqlAlchemyUserRepository."""

    @pytest.mark.asyncio
    async def test_create_user_success(
        self, user_repository: SqlAlchemyUserRepository, user_db_session: AsyncSession
    ) -> None:
        """Test creating a new user successfully."""
        email = "newuser@example.com"
        hashed_password = "hashed_password_123"

        result = await user_repository.create_user(email, hashed_password)

        assert result.email == email
        assert result.password == hashed_password
        assert result.is_active is True
        assert result.last_login_at is None
        assert result.created_at is not None
        assert isinstance(result, User)

        # Verify persistence
        persisted = await user_db_session.execute(
            __import__("sqlalchemy").select(UserModel).where(UserModel.email == email)
        )
        persisted_user = persisted.scalar_one_or_none()
        assert persisted_user is not None
        assert persisted_user.password == hashed_password

    @pytest.mark.asyncio
    async def test_create_multiple_users(
        self, user_repository: SqlAlchemyUserRepository, user_db_session: AsyncSession
    ) -> None:
        """Test creating multiple users."""
        users_data = [
            ("user1@example.com", "hash1"),
            ("user2@example.com", "hash2"),
            ("user3@example.com", "hash3"),
        ]

        results = []
        for email, password in users_data:
            result = await user_repository.create_user(email, password)
            results.append(result)

        assert len(results) == 3
        assert all(isinstance(u, User) for u in results)
        assert [u.email for u in results] == [
            "user1@example.com",
            "user2@example.com",
            "user3@example.com",
        ]

    @pytest.mark.asyncio
    async def test_get_by_email_success(
        self, user_repository: SqlAlchemyUserRepository, user_db_session: AsyncSession
    ) -> None:
        """Test retrieving a user by email."""
        email = "findme@example.com"
        hashed_password = "super_secret_hash"

        # Create user
        created_user = await user_repository.create_user(email, hashed_password)

        # Retrieve user
        result = await user_repository.get_by_email(email)

        assert result is not None
        assert result.email == email
        assert result.password == hashed_password
        assert result.id == created_user.id
        assert isinstance(result, User)

    @pytest.mark.asyncio
    async def test_get_by_email_not_found(
        self, user_repository: SqlAlchemyUserRepository
    ) -> None:
        """Test retrieving a non-existent user by email returns None."""
        result = await user_repository.get_by_email("nonexistent@example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_email_case_sensitive(
        self, user_repository: SqlAlchemyUserRepository
    ) -> None:
        """Test that email lookup is case-sensitive in database."""
        email_lower = "test@example.com"
        email_upper = "TEST@EXAMPLE.COM"

        # Create user with lowercase email
        await user_repository.create_user(email_lower, "hash1")

        # Try to find with uppercase - should not find (case-sensitive)
        result = await user_repository.get_by_email(email_upper)

        # Note: This test documents the current behavior.
        # Most email systems should be case-insensitive, but the implementation
        # currently performs case-sensitive lookups.
        assert result is None

    @pytest.mark.asyncio
    async def test_create_user_with_multiple_fields(
        self, user_repository: SqlAlchemyUserRepository, user_db_session: AsyncSession
    ) -> None:
        """Test that created user has all expected fields."""
        email = "complete@example.com"
        password = "hashed_complete"

        result = await user_repository.create_user(email, password)

        # Verify all fields are present and accessible
        assert hasattr(result, "id")
        assert hasattr(result, "email")
        assert hasattr(result, "password")
        assert hasattr(result, "is_active")
        assert hasattr(result, "last_login_at")
        assert hasattr(result, "created_at")

        # Verify types
        assert isinstance(result.id, __import__("uuid").UUID)
        assert isinstance(result.email, str)
        assert isinstance(result.password, str)
        assert isinstance(result.is_active, bool)
        assert result.last_login_at is None
        assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_user_schema_returns_not_model(
        self, user_repository: SqlAlchemyUserRepository
    ) -> None:
        """Test that repository returns Pydantic User schema, not SQLAlchemy model."""
        email = "schema@example.com"
        password = "hash_schema"

        result = await user_repository.create_user(email, password)

        # Verify it's a Pydantic model, not SQLAlchemy model
        assert isinstance(result, User)
        assert not isinstance(result, UserModel)
        assert hasattr(result, "model_validate")

    @pytest.mark.asyncio
    async def test_get_by_email_returns_schema(
        self, user_repository: SqlAlchemyUserRepository
    ) -> None:
        """Test that get_by_email returns proper schema."""
        email = "get_schema@example.com"
        password = "hash_get"

        await user_repository.create_user(email, password)
        result = await user_repository.get_by_email(email)

        assert isinstance(result, User)
        assert not isinstance(result, UserModel)

    @pytest.mark.asyncio
    async def test_create_user_with_special_characters_in_email(
        self, user_repository: SqlAlchemyUserRepository, user_db_session: AsyncSession
    ) -> None:
        """Test creating user with special characters in email."""
        email = "user+tag@example.co.uk"
        password = "hash_special"

        result = await user_repository.create_user(email, password)

        assert result.email == email

        # Verify retrieval
        retrieved = await user_repository.get_by_email(email)
        assert retrieved is not None
        assert retrieved.email == email

    @pytest.mark.asyncio
    async def test_create_user_with_long_email(
        self, user_repository: SqlAlchemyUserRepository, user_db_session: AsyncSession
    ) -> None:
        """Test creating user with very long email."""
        email = "a" * 50 + "@example.com"
        password = "hash_long"

        result = await user_repository.create_user(email, password)

        assert result.email == email

        # Verify retrieval
        retrieved = await user_repository.get_by_email(email)
        assert retrieved is not None
        assert retrieved.email == email

    @pytest.mark.asyncio
    async def test_create_user_with_long_password_hash(
        self, user_repository: SqlAlchemyUserRepository
    ) -> None:
        """Test creating user with very long password hash."""
        email = "longhash@example.com"
        password = "x" * 500

        result = await user_repository.create_user(email, password)

        assert result.password == password

    @pytest.mark.asyncio
    async def test_get_by_email_multiple_users(
        self, user_repository: SqlAlchemyUserRepository
    ) -> None:
        """Test retrieving correct user when multiple users exist."""
        emails = ["user1@example.com", "user2@example.com", "user3@example.com"]

        # Create multiple users
        for email in emails:
            await user_repository.create_user(email, "hash")

        # Retrieve each and verify correct one is returned
        for email in emails:
            result = await user_repository.get_by_email(email)
            assert result is not None
            assert result.email == email

    @pytest.mark.asyncio
    async def test_user_timestamps(
        self, user_repository: SqlAlchemyUserRepository
    ) -> None:
        """Test that user timestamps are set correctly."""
        email = "timestamp@example.com"
        password = "hash_time"

        result = await user_repository.create_user(email, password)

        assert result.created_at is not None
        # Just verify the timestamp exists and is recent (within last 5 seconds)
        now = datetime.now() if result.created_at.tzinfo is None else datetime.now(UTC)
        time_diff = abs((now - result.created_at).total_seconds())
        assert time_diff < 5, "Timestamp should be recent"
        assert result.last_login_at is None

    @pytest.mark.asyncio
    async def test_create_user_default_fields(
        self, user_repository: SqlAlchemyUserRepository
    ) -> None:
        """Test that default fields are set correctly on user creation."""
        email = "defaults@example.com"
        password = "hash_defaults"

        result = await user_repository.create_user(email, password)

        # Check default values
        assert result.is_active is True
        assert result.last_login_at is None

    @pytest.mark.asyncio
    async def test_create_user_produces_unique_ids(
        self, user_repository: SqlAlchemyUserRepository
    ) -> None:
        """Test that each created user has a unique ID."""
        user1 = await user_repository.create_user("user1@ex.com", "hash1")
        user2 = await user_repository.create_user("user2@ex.com", "hash2")
        user3 = await user_repository.create_user("user3@ex.com", "hash3")

        ids = {user1.id, user2.id, user3.id}
        assert len(ids) == 3  # All unique
