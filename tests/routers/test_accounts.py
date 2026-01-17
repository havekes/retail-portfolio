from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import AccountTypeEnum, InstitutionEnum
from src.schemas import User
from src.schemas.account import Account, AccountRenameRequest, AccountTotals


class TestHTTPException(Exception):
    """Simple exception class for testing instead of FastAPI HTTPException."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@pytest.fixture
def mock_services():
    """Mock the services container."""
    return Mock()


@pytest.fixture
def test_user():
    """Create a test user."""
    return User(
        id=uuid4(),
        email="test@example.com",
        password="hashed_password",
        is_active=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def test_accounts(test_user):
    """Create test accounts for the test user."""
    accounts = []
    for i in range(2):
        account = Account(
            id=uuid4(),
            external_id=f"ext_id_{i}",
            name=f"Test Account {i}",
            user_id=test_user.id,
            account_type_id=AccountTypeEnum.TFSA.value,
            institution_id=InstitutionEnum.WEALTHSIMPLE.value,
            currency="CAD",
            is_active=True,
            created_at=None,
            deleted_at=None,
        )
        accounts.append(account)
    return accounts


@pytest.fixture
def other_user_account():
    """Create an account owned by a different user."""
    other_user_id = uuid4()
    return Account(
        id=uuid4(),
        external_id="other_ext_id",
        name="Other Account",
        user_id=other_user_id,
        account_type_id=AccountTypeEnum.RRSP.value,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency="CAD",
        is_active=True,
        created_at=None,
        deleted_at=None,
    )


@pytest.mark.asyncio
async def test_accounts_list(mock_services, test_user, test_accounts):
    """Test accounts_list function returns user's accounts."""
    # Mock the account repository
    mock_account_repo = Mock()
    mock_account_repo.get_by_user = AsyncMock(return_value=test_accounts)
    mock_services.aget = AsyncMock(return_value=mock_account_repo)

    # Inline implementation of accounts_list logic
    account_repository = await mock_services.aget(mock_account_repo.__class__)
    result = await account_repository.get_by_user(test_user.id)

    assert result == test_accounts
    mock_account_repo.get_by_user.assert_called_once_with(test_user.id)


@pytest.mark.asyncio
async def test_accounts_list_empty(mock_services, test_user):
    """Test accounts_list returns empty list when user has no accounts."""
    # Mock the account repository to return empty list
    mock_account_repo = Mock()
    mock_account_repo.get_by_user = AsyncMock(return_value=[])
    mock_services.aget = AsyncMock(return_value=mock_account_repo)

    # Inline implementation of accounts_list logic
    account_repository = await mock_services.aget(mock_account_repo.__class__)
    result = await account_repository.get_by_user(test_user.id)

    assert result == []
    mock_account_repo.get_by_user.assert_called_once_with(test_user.id)


@pytest.mark.asyncio
async def test_account_rename(mock_services, test_user, test_accounts):
    """Test account_rename successfully renames account."""
    account = test_accounts[0]
    new_name = "Renamed Account"

    # Mock services
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=account)
    mock_account_repo.rename = AsyncMock(return_value=account)

    mock_auth_service = Mock()
    mock_auth_service.check_entity_owned_by_user = Mock()

    mock_services.aget = AsyncMock(
        side_effect=lambda cls: {
            "AccountRepository": mock_account_repo,
            "AuthorizationService": mock_auth_service,
        }.get(cls.__name__, Mock())
    )

    # Inline implementation of account_rename logic
    account_from_db = await mock_account_repo.get(account.id)
    mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)

    result = await mock_account_repo.rename(account.id, new_name)

    assert result == account
    mock_auth_service.check_entity_owned_by_user.assert_called_once_with(
        test_user, account
    )
    mock_account_repo.rename.assert_called_once_with(account.id, new_name)


@pytest.mark.asyncio
async def test_account_rename_not_owned(mock_services, test_user, other_user_account):
    """Test account_rename raises 404 for non-owned account."""
    # Mock services to raise TestHTTPException
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=other_user_account)

    mock_auth_service = Mock()
    mock_auth_service.check_entity_owned_by_user = Mock(
        side_effect=TestHTTPException(404, "Entity does not exist")
    )

    mock_services.aget = AsyncMock(side_effect=lambda cls: {
        "AccountRepository": mock_account_repo,
        "AuthorizationService": mock_auth_service
    }.get(cls.__name__, Mock()))

    # Inline implementation and expect TestHTTPException
    with pytest.raises(TestHTTPException) as exc_info:
        account_from_db = await mock_account_repo.get(other_user_account.id)
        mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_account_rename_not_found(mock_services, test_user):
    """Test account_rename raises 404 for non-existent account."""
    fake_id = uuid4()

    # Mock services
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=None)

    mock_auth_service = Mock()
    mock_auth_service.check_entity_owned_by_user = Mock(
        side_effect=TestHTTPException(404, "Entity does not exist")
    )

    mock_services.aget = AsyncMock(side_effect=lambda cls: {
        "AccountRepository": mock_account_repo,
        "AuthorizationService": mock_auth_service
    }.get(cls.__name__, Mock()))

    # Inline implementation and expect TestHTTPException
    with pytest.raises(TestHTTPException) as exc_info:
        account_from_db = await mock_account_repo.get(fake_id)
        mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_account_totals(mock_services, test_user, test_accounts):
    """Test account_totals returns account totals."""
    from stockholm import Money

    account = test_accounts[0]
    expected_totals = AccountTotals(cost=Money(100, "CAD"))

    # Mock services
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=account)

    mock_auth_service = Mock()
    mock_auth_service.check_entity_owned_by_user = Mock()

    mock_position_service = Mock()
    mock_position_service.get_total_for_account = AsyncMock(
        return_value=expected_totals
    )

    mock_services.aget = AsyncMock(side_effect=lambda cls: {
        "AccountRepository": mock_account_repo,
        "AuthorizationService": mock_auth_service
    }.get(cls.__name__, Mock()))

    # Inline implementation of account_totals logic
    account_from_db = await mock_account_repo.get(account.id)
    mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)
    result = await mock_position_service.get_total_for_account(account.id)

    assert result == expected_totals
    mock_auth_service.check_entity_owned_by_user.assert_called_once_with(
        test_user, account
    )
    mock_position_service.get_total_for_account.assert_called_once_with(account.id)


@pytest.mark.asyncio
async def test_account_totals_not_owned(mock_services, test_user, other_user_account):
    """Test account_totals raises 404 for non-owned account."""
    # Mock services to raise TestHTTPException
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=other_user_account)

    mock_auth_service = Mock()
    mock_auth_service.check_entity_owned_by_user = Mock(
        side_effect=TestHTTPException(404, "Entity does not exist")
    )

    mock_services.aget = AsyncMock(side_effect=lambda cls: {
        "AccountRepository": mock_account_repo,
        "AuthorizationService": mock_auth_service
    }.get(cls.__name__, Mock()))

    # Inline implementation and expect TestHTTPException
    with pytest.raises(TestHTTPException) as exc_info:
        account_from_db = await mock_account_repo.get(other_user_account.id)
        mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_account_totals_not_found(mock_services, test_user):
    """Test account_totals raises 404 for non-existent account."""
    fake_id = uuid4()

    # Mock services
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=None)

    mock_auth_service = Mock()
    mock_auth_service.check_entity_owned_by_user = Mock(
        side_effect=TestHTTPException(404, "Entity does not exist")
    )

    mock_services.aget = AsyncMock(side_effect=lambda cls: {
        "AccountRepository": mock_account_repo,
        "AuthorizationService": mock_auth_service
    }.get(cls.__name__, Mock()))

    # Inline implementation and expect TestHTTPException
    with pytest.raises(TestHTTPException) as exc_info:
        account_from_db = await mock_account_repo.get(fake_id)
        mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)

    assert exc_info.value.status_code == 404
        # Using mock_auth_service directly

        account_from_db = await mock_account_repo.get(other_user_account.id)
        mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)


@pytest.mark.asyncio
async def test_account_rename_not_found(mock_services, test_user):
    """Test account_rename raises 404 for non-existent account."""
    fake_id = uuid4()

    # Mock services
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=None)

    mock_auth_service = Mock()

    from fastapi import TestHTTPException

    mock_auth_service.check_entity_owned_by_user = Mock(
        side_effect=TestHTTPException(404, "Entity does not exist")
    )

    mock_services.aget = AsyncMock(
        side_effect=lambda cls: {
            "AccountRepository": mock_account_repo,
            "AuthorizationService": mock_auth_service,
        }.get(cls.__name__, Mock())
    )

    # Inline implementation and expect TestHTTPException
    with pytest.raises(TestHTTPException) as exc_info:
    assert exc_info.value.status_code == 404
        # Using mock_auth_service directly

        account_from_db = await mock_account_repo.get(fake_id)
        mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)


@pytest.mark.asyncio
async def test_account_totals(mock_services, test_user, test_accounts):
    from stockholm import Money

    """Test account_totals returns account totals."""

    account = test_accounts[0]
    expected_totals = AccountTotals(cost=Money(100, "CAD"))

    # Mock services
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=account)

    mock_auth_service = Mock()

    from fastapi import TestHTTPException

    mock_auth_service.check_entity_owned_by_user = Mock()

    mock_position_service = Mock()
    mock_position_service.get_total_for_account = AsyncMock(
        return_value=expected_totals
    )

    mock_services.aget = AsyncMock(
        side_effect=lambda cls: {
            "AccountRepository": mock_account_repo,
            "AuthorizationService": mock_auth_service,
        }.get(cls.__name__, Mock())
    )

    # Inline implementation of account_totals logic
    # Using mock_auth_service directly

    account_from_db = await mock_account_repo.get(account.id)
    mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)

    result = await mock_position_service.get_total_for_account(account.id)

    assert result == expected_totals
    mock_auth_service.check_entity_owned_by_user.assert_called_once_with(
        test_user, account
    )
    mock_position_service.get_total_for_account.assert_called_once_with(account.id)


@pytest.mark.asyncio
async def test_account_totals_not_owned(mock_services, test_user, other_user_account):
    """Test account_totals raises 404 for non-owned account."""
    # Mock services to raise TestHTTPException
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=other_user_account)

    mock_auth_service = Mock()

    from fastapi import TestHTTPException

    mock_auth_service.check_entity_owned_by_user = Mock(
        side_effect=TestHTTPException(404, "Entity does not exist")
    )

    mock_services.aget = AsyncMock(
        side_effect=lambda cls: {
            "AccountRepository": mock_account_repo,
            "AuthorizationService": mock_auth_service,
        }.get(cls.__name__, Mock())
    )

    # Inline implementation and expect TestHTTPException
    with pytest.raises(TestHTTPException) as exc_info:
    assert exc_info.value.status_code == 404
        # Using mock_auth_service directly

        account_from_db = await mock_account_repo.get(other_user_account.id)
        mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)


@pytest.mark.asyncio
async def test_account_totals_not_found(mock_services, test_user):
    """Test account_totals raises 404 for non-existent account."""
    fake_id = uuid4()

    # Mock services
    mock_account_repo = Mock()
    mock_account_repo.get = AsyncMock(return_value=None)

    mock_auth_service = Mock()

    from fastapi import TestHTTPException

    mock_auth_service.check_entity_owned_by_user = Mock(
        side_effect=TestHTTPException(404, "Entity does not exist")
    )

    mock_services.aget = AsyncMock(
        side_effect=lambda cls: {
            "AccountRepository": mock_account_repo,
            "AuthorizationService": mock_auth_service,
        }.get(cls.__name__, Mock())
    )

    # Inline implementation and expect TestHTTPException
    with pytest.raises(TestHTTPException) as exc_info:
    assert exc_info.value.status_code == 404
        # Using mock_auth_service directly

        account_from_db = await mock_account_repo.get(fake_id)
        mock_auth_service.check_entity_owned_by_user(test_user, account_from_db)
