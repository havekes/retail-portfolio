"""Unit tests for SqlAlchemyExternalUserRepository."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from src.models import Base
from src.models.external_user import ExternalUser as ExternalUserModel
from src.models.institution import Institution as InstitutionModel
from src.models.user import User as UserModel
from src.repositories.sqlalchemy.sqlalchemy_external_user import (
    SqlAlchemyExternalUserRepository,
)
from src.schemas.external_user import FullExternalUser


@pytest_asyncio.fixture(scope="function")
async def external_user_test_engine() -> AsyncEngine:
    """Create test database engine for external user repository tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def external_user_db_session(
    external_user_test_engine: AsyncEngine,
) -> AsyncSession:
    """Provide a fresh database session for each test."""
    from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: PLC0415

    async_session = async_sessionmaker(
        external_user_test_engine, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def external_user_repository(
    external_user_db_session: AsyncSession,
) -> SqlAlchemyExternalUserRepository:
    """Create a repository instance for testing."""
    return SqlAlchemyExternalUserRepository(session=external_user_db_session)


@pytest_asyncio.fixture(scope="function")
async def seed_external_user_data(external_user_db_session: AsyncSession) -> tuple:
    """Seed necessary reference data for external user tests."""
    # Create users
    user1 = UserModel(
        id=uuid4(),
        email="user1@example.com",
        password="hashed",
        is_active=True,
        created_at=datetime.now(UTC),
    )

    user2 = UserModel(
        id=uuid4(),
        email="user2@example.com",
        password="hashed",
        is_active=True,
        created_at=datetime.now(UTC),
    )

    # Create institutions
    institution1 = InstitutionModel(
        id=1,
        name="Wealthsimple",
        country="CA",
        is_active=True,
    )

    institution2 = InstitutionModel(
        id=2,
        name="Interactive Brokers",
        country="US",
        is_active=True,
    )

    external_user_db_session.add_all([user1, user2, institution1, institution2])
    await external_user_db_session.commit()
    await external_user_db_session.refresh(user1)
    await external_user_db_session.refresh(user2)
    await external_user_db_session.refresh(institution1)
    await external_user_db_session.refresh(institution2)

    return (user1, user2, institution1, institution2)


class TestSqlAlchemyExternalUserRepository:
    """Test suite for SqlAlchemyExternalUserRepository."""

    @pytest.mark.asyncio
    async def test_create_external_user_success(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test creating a new external user successfully."""
        user, _, institution, _ = seed_external_user_data
        external_user_id = uuid4()
        now = datetime.now(UTC)

        external_user_schema = FullExternalUser(
            id=external_user_id,
            user_id=user.id,
            institution_id=institution.id,
            external_user_id="ext_user_123",
            display_name="John Doe",
            last_used_at=now,
        )

        result = await external_user_repository.create(external_user_schema)

        assert result.id == external_user_id
        assert result.user_id == user.id
        assert result.institution_id == institution.id
        assert result.external_user_id == "ext_user_123"
        assert result.display_name == "John Doe"
        assert isinstance(result, FullExternalUser)

        # Verify persistence
        persisted = await external_user_db_session.get(
            ExternalUserModel, external_user_id
        )
        assert persisted is not None

    @pytest.mark.asyncio
    async def test_get_external_user_success(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test retrieving an external user by ID."""
        user, _, institution, _ = seed_external_user_data
        external_user_id = uuid4()
        now = datetime.now(UTC)

        # Create external user directly in database
        external_user_model = ExternalUserModel(
            id=external_user_id,
            user_id=user.id,
            institution_id=institution.id,
            external_user_id="ext_456",
            display_name="Jane Smith",
            last_used_at=now,
        )
        external_user_db_session.add(external_user_model)
        await external_user_db_session.commit()

        result = await external_user_repository.get(external_user_id)

        assert result is not None
        assert result.id == external_user_id
        assert result.external_user_id == "ext_456"
        assert result.display_name == "Jane Smith"
        assert isinstance(result, FullExternalUser)

    @pytest.mark.asyncio
    async def test_get_external_user_not_found(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
    ) -> None:
        """Test retrieving a non-existent external user returns None."""
        result = await external_user_repository.get(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_user_and_institution_single_result(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test retrieving external users by user and institution."""
        user1, _, institution1, _ = seed_external_user_data

        external_user_model = ExternalUserModel(
            id=uuid4(),
            user_id=user1.id,
            institution_id=institution1.id,
            external_user_id="single_user",
            display_name="Single",
            last_used_at=datetime.now(UTC),
        )
        external_user_db_session.add(external_user_model)
        await external_user_db_session.commit()

        result = await external_user_repository.get_by_user_and_institution(
            user1.id, institution1.id
        )

        assert len(result) == 1
        assert result[0].external_user_id == "single_user"
        assert result[0].display_name == "Single"

    @pytest.mark.asyncio
    async def test_get_by_user_and_institution_multiple_results(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test retrieving multiple external users for same user/institution."""
        user1, _, institution1, _ = seed_external_user_data

        # Create multiple external users for the same user and institution
        for i in range(3):
            external_user_model = ExternalUserModel(
                id=uuid4(),
                user_id=user1.id,
                institution_id=institution1.id,
                external_user_id=f"ext_user_{i}",
                display_name=f"User {i}",
                last_used_at=datetime.now(UTC),
            )
            external_user_db_session.add(external_user_model)

        await external_user_db_session.commit()

        result = await external_user_repository.get_by_user_and_institution(
            user1.id, institution1.id
        )

        assert len(result) == 3
        assert all(isinstance(eu, FullExternalUser) for eu in result)

    @pytest.mark.asyncio
    async def test_get_by_user_and_institution_empty_result(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        seed_external_user_data: tuple,
    ) -> None:
        """Test retrieving external users with no results."""
        user, _, institution, _ = seed_external_user_data

        result = await external_user_repository.get_by_user_and_institution(
            user.id, institution.id
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_user_and_institution_different_users(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test that external users are correctly filtered by user."""
        user1, user2, institution1, _ = seed_external_user_data

        # Create external user for user1
        external_user1 = ExternalUserModel(
            id=uuid4(),
            user_id=user1.id,
            institution_id=institution1.id,
            external_user_id="user1_ext",
            display_name="User1 External",
            last_used_at=datetime.now(UTC),
        )

        # Create external user for user2
        external_user2 = ExternalUserModel(
            id=uuid4(),
            user_id=user2.id,
            institution_id=institution1.id,
            external_user_id="user2_ext",
            display_name="User2 External",
            last_used_at=datetime.now(UTC),
        )

        external_user_db_session.add_all([external_user1, external_user2])
        await external_user_db_session.commit()

        # Get external users for user1
        result1 = await external_user_repository.get_by_user_and_institution(
            user1.id, institution1.id
        )
        # Get external users for user2
        result2 = await external_user_repository.get_by_user_and_institution(
            user2.id, institution1.id
        )

        assert len(result1) == 1
        assert result1[0].external_user_id == "user1_ext"
        assert len(result2) == 1
        assert result2[0].external_user_id == "user2_ext"

    @pytest.mark.asyncio
    async def test_get_unique_success(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test retrieving a unique external user by user, institution, and username."""
        user, _, institution, _ = seed_external_user_data

        external_user_model = ExternalUserModel(
            id=uuid4(),
            user_id=user.id,
            institution_id=institution.id,
            external_user_id="unique_username",
            display_name="Unique User",
            last_used_at=datetime.now(UTC),
        )
        external_user_db_session.add(external_user_model)
        await external_user_db_session.commit()

        result = await external_user_repository.get_unique(
            user.id, institution.id, "unique_username"
        )

        assert result is not None
        assert result.external_user_id == "unique_username"
        assert isinstance(result, FullExternalUser)

    @pytest.mark.asyncio
    async def test_get_unique_not_found(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        seed_external_user_data: tuple,
    ) -> None:
        """Test retrieving non-existent unique external user returns None."""
        user, _, institution, _ = seed_external_user_data

        result = await external_user_repository.get_unique(
            user.id, institution.id, "nonexistent_username"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_exists_true(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test checking if external user exists - exists."""
        user, _, institution, _ = seed_external_user_data

        external_user_model = ExternalUserModel(
            id=uuid4(),
            user_id=user.id,
            institution_id=institution.id,
            external_user_id="exists_user",
            display_name="Exists",
            last_used_at=datetime.now(UTC),
        )
        external_user_db_session.add(external_user_model)
        await external_user_db_session.commit()

        result = await external_user_repository.exists(
            user.id, institution.id, "exists_user"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        seed_external_user_data: tuple,
    ) -> None:
        """Test checking if external user exists - does not exist."""
        user, _, institution, _ = seed_external_user_data

        result = await external_user_repository.exists(
            user.id, institution.id, "nonexistent_user"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_last_used_at_success(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test updating last_used_at timestamp."""
        user, _, institution, _ = seed_external_user_data
        external_user_id = uuid4()
        old_time = datetime.now(UTC) - timedelta(days=1)

        # Create external user with old timestamp
        external_user_model = ExternalUserModel(
            id=external_user_id,
            user_id=user.id,
            institution_id=institution.id,
            external_user_id="update_time",
            display_name="Update Time",
            last_used_at=old_time,
        )
        external_user_db_session.add(external_user_model)
        await external_user_db_session.commit()

        # Update last_used_at
        external_user_schema = FullExternalUser(
            id=external_user_id,
            user_id=user.id,
            institution_id=institution.id,
            external_user_id="update_time",
            display_name="Update Time",
            last_used_at=old_time,
        )

        await external_user_repository.update_last_used_at(external_user_schema)

        # Refresh the session to get latest data
        await external_user_db_session.refresh(external_user_model)

        # Verify update - timestamp should be more recent
        assert external_user_model.last_used_at is not None
        # Make sure both timestamps are aware or naive for comparison
        if (
            external_user_model.last_used_at.tzinfo is None
            and old_time.tzinfo is not None
        ):
            old_time = old_time.replace(tzinfo=None)
        elif (
            external_user_model.last_used_at.tzinfo is not None
            and old_time.tzinfo is None
        ):
            external_user_model.last_used_at = external_user_model.last_used_at.replace(
                tzinfo=None
            )
        assert external_user_model.last_used_at > old_time

    @pytest.mark.asyncio
    async def test_create_returns_schema(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        seed_external_user_data: tuple,
    ) -> None:
        """Test that create returns FullExternalUser schema, not model."""
        user, _, institution, _ = seed_external_user_data

        external_user_schema = FullExternalUser(
            id=uuid4(),
            user_id=user.id,
            institution_id=institution.id,
            external_user_id="schema_test",
            display_name="Schema Test",
            last_used_at=datetime.now(UTC),
        )

        result = await external_user_repository.create(external_user_schema)

        assert isinstance(result, FullExternalUser)
        assert not isinstance(result, ExternalUserModel)

    @pytest.mark.asyncio
    async def test_get_by_user_and_institution_different_institutions(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test filtering by different institutions."""
        user, _, institution1, institution2 = seed_external_user_data

        # Create external users in different institutions
        eu1 = ExternalUserModel(
            id=uuid4(),
            user_id=user.id,
            institution_id=institution1.id,
            external_user_id="inst1_user",
            display_name="Institution 1",
            last_used_at=datetime.now(UTC),
        )

        eu2 = ExternalUserModel(
            id=uuid4(),
            user_id=user.id,
            institution_id=institution2.id,
            external_user_id="inst2_user",
            display_name="Institution 2",
            last_used_at=datetime.now(UTC),
        )

        external_user_db_session.add_all([eu1, eu2])
        await external_user_db_session.commit()

        # Get from institution 1
        result1 = await external_user_repository.get_by_user_and_institution(
            user.id, institution1.id
        )
        # Get from institution 2
        result2 = await external_user_repository.get_by_user_and_institution(
            user.id, institution2.id
        )

        assert len(result1) == 1
        assert result1[0].institution_id == institution1.id
        assert len(result2) == 1
        assert result2[0].institution_id == institution2.id

    @pytest.mark.asyncio
    async def test_external_user_with_null_display_name(
        self,
        external_user_repository: SqlAlchemyExternalUserRepository,
        external_user_db_session: AsyncSession,
        seed_external_user_data: tuple,
    ) -> None:
        """Test external user with null display_name."""
        user, _, institution, _ = seed_external_user_data
        external_user_id = uuid4()

        # Create external user without display_name in database
        external_user_model = ExternalUserModel(
            id=external_user_id,
            user_id=user.id,
            institution_id=institution.id,
            external_user_id="no_display_name",
            display_name="",
            last_used_at=datetime.now(UTC),
        )
        external_user_db_session.add(external_user_model)
        await external_user_db_session.commit()

        result = await external_user_repository.get(external_user_id)

        assert result is not None
        assert result.display_name == ""
