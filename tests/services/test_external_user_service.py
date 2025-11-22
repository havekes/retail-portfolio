from unittest.mock import AsyncMock, Mock

import pytest

from uuid import uuid4
from datetime import UTC, datetime

PASSWORD = "hashed_password"

from src.enums import InstitutionEnum
from src.repositories.external_user import ExternalUserRepository
from src.schemas.external_user import FullExternalUser
from src.schemas.user import User
from src.services.external_user import ExternalUserService


@pytest.mark.asyncio
async def test_get_or_create_existing_external_user():
    # Arrange
    mock_external_user_repo = Mock(spec=ExternalUserRepository)
    service = ExternalUserService(mock_external_user_repo)

    user = User(id=uuid4(), email="test@example.com", password=PASSWORD, is_active=True, last_login_at=None, created_at=datetime.now(UTC))
    institution = InstitutionEnum.WEALTHSIMPLE
    external_user_id = "ext_id"

    existing_external_user = FullExternalUser(
        uuid=uuid4(),
        user_id=user.id,
        institution_id=institution.value,
        external_user_id=external_user_id,
    )

    mock_external_user_repo.get = AsyncMock(return_value=existing_external_user)
    mock_external_user_repo.create = AsyncMock()  # Should not be called

    # Act
    result = await service.get_or_create(user, institution, external_user_id)

    # Assert
    assert result == existing_external_user
    mock_external_user_repo.get.assert_called_once_with(user.id, institution.value, external_user_id)
    mock_external_user_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_new_external_user():
    # Arrange
    mock_external_user_repo = Mock(spec=ExternalUserRepository)
    service = ExternalUserService(mock_external_user_repo)

    user = User(id=uuid4(), email="test@example.com", password=PASSWORD, is_active=True, last_login_at=None, created_at=datetime.now(UTC))
    institution = InstitutionEnum.WEALTHSIMPLE
    external_user_id = "ext_id"

    new_external_user = FullExternalUser(
        uuid=uuid4(),
        user_id=user.id,
        institution_id=institution.value,
        external_user_id=external_user_id,
    )

    mock_external_user_repo.get = AsyncMock(return_value=None)
    mock_external_user_repo.create = AsyncMock(return_value=new_external_user)

    # Act
    result = await service.get_or_create(user, institution, external_user_id)

    # Assert
    assert result == new_external_user
    mock_external_user_repo.get.assert_called_once_with(user.id, institution.value, external_user_id)
    mock_external_user_repo.create.assert_called_once()
    args, kwargs = mock_external_user_repo.create.call_args
    created_obj = args[0]
    assert created_obj.user_id == user.id
    assert created_obj.institution_id == institution.value
    assert created_obj.external_user_id == external_user_id
