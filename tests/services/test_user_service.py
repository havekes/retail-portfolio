from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import InstitutionEnum
from src.repositories.external_user import ExternalUserRepository
from src.repositories.user import UserRepository
from src.schemas.external_user import FullExternalUser
from src.schemas.user import User
from src.services.user import UserService

PASSWORD = "hashed_password"


@pytest.mark.asyncio
async def test_get_current_user_success():
    # Arrange
    mock_user_repo = Mock(spec=UserRepository)
    user = User(
        id=uuid4(),
        email="greg@havek.es",
        password=PASSWORD,
        is_active=True,
        last_login_at=None,
        created_at=datetime.now(UTC)
    )
    mock_user_repo.get_by_email = AsyncMock(return_value=user)
    mock_external_user_repo = Mock(spec=ExternalUserRepository)
    service = UserService(mock_user_repo, mock_external_user_repo)

    # Act
    result = await service.get_current_user()

    # Assert
    assert result == user
    mock_user_repo.get_by_email.assert_called_once_with("greg@havek.es")


@pytest.mark.asyncio
async def test_get_current_user_not_found():
    # Arrange
    mock_user_repo = Mock(spec=UserRepository)
    mock_user_repo.get_by_email = AsyncMock(return_value=None)
    mock_external_user_repo = Mock(spec=ExternalUserRepository)
    service = UserService(mock_user_repo, mock_external_user_repo)

    # Act & Assert
    with pytest.raises(SystemError, match="User not found"):
        await service.get_current_user()
    mock_user_repo.get_by_email.assert_called_once_with("greg@havek.es")


@pytest.mark.asyncio
async def test_get_current_user_external_account_ids():
    # Arrange
    mock_user_repo = Mock(spec=UserRepository)
    mock_external_repo = Mock(spec=ExternalUserRepository)
    user = User(
        id=uuid4(),
        email="greg@havek.es",
        password=PASSWORD,
        is_active=True,
        last_login_at=None,
        created_at=datetime.now(UTC)
    )
    accounts = [
        FullExternalUser(
            id=uuid4(),
            user_id=user.id,
            institution_id=InstitutionEnum.WEALTHSIMPLE.value,
            external_user_id="123"
        ),
        FullExternalUser(
            id=uuid4(),
            user_id=user.id,
            institution_id=InstitutionEnum.WEALTHSIMPLE.value,
            external_user_id="456"
        )
    ]
    mock_user_repo.get_by_email = AsyncMock(return_value=user)
    mock_external_repo.get_by_user_and_institution = AsyncMock(return_value=accounts)
    mock_external_user_repo = Mock(spec=ExternalUserRepository)
    service = UserService(mock_user_repo, mock_external_user_repo)
    service.external_user_repository = mock_external_repo

    institution = InstitutionEnum.WEALTHSIMPLE
    # Act
    result = await service.get_current_user_external_account_ids(institution)

    # Assert
    external_ids = list(result)
    assert external_ids == ["123", "456"]
    mock_user_repo.get_by_email.assert_called_once_with("greg@havek.es")
    mock_external_repo.get_by_user_and_institution.assert_called_once_with(
        user.id, institution.value
    )


@pytest.mark.asyncio
async def test_get_current_user_external_account_ids_no_accounts():
    # Arrange
    mock_user_repo = Mock(spec=UserRepository)
    mock_external_repo = Mock(spec=ExternalUserRepository)
    user = User(
        id=uuid4(),
        email="greg@havek.es",
        password=PASSWORD,
        is_active=True,
        last_login_at=None,
        created_at=datetime.now(UTC)
    )
    accounts = []
    mock_user_repo.get_by_email = AsyncMock(return_value=user)
    mock_external_repo.get_by_user_and_institution = AsyncMock(return_value=accounts)
    mock_external_user_repo = Mock(spec=ExternalUserRepository)
    service = UserService(mock_user_repo, mock_external_user_repo)
    service.external_user_repository = mock_external_repo

    institution = InstitutionEnum.WEALTHSIMPLE
    # Act
    result = await service.get_current_user_external_account_ids(institution)

    # Assert
    external_ids = list(result)
    assert external_ids == []
    mock_user_repo.get_by_email.assert_called_once_with("greg@havek.es")
    mock_external_repo.get_by_user_and_institution.assert_called_once_with(
        user.id, institution.value
    )
