from datetime import datetime, UTC
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.schemas.user import User
from src.services.authorization import AuthorizationService
from src.services.user import UserService


class TestAuthorizationService:
    """Test suite for AuthorizationService."""

    @pytest.fixture
    def mock_user_service(self):
        return Mock(spec=UserService)

    @pytest.fixture
    def auth_service(self, mock_user_service):
        return AuthorizationService(mock_user_service)

    def test_check_entity_owned_by_user_success(self, auth_service):
        """Test check_entity_owned_by_user when entity belongs to user."""
        user = User(id=uuid4(), email="user@example.com", password="hash", is_active=True, last_login_at=None, created_at=datetime.now(UTC))

        class MockEntity:
            user_id = user.id

        entity = MockEntity()
        # Should not raise
        auth_service.check_entity_owned_by_user(user, entity)

    def test_check_entity_owned_by_user_none_entity(self, auth_service):
        """Test check_entity_owned_by_user with None entity."""
        user = User(id=uuid4(), email="user@example.com", password="hash", is_active=True, last_login_at=None, created_at=datetime.now(UTC))

        with pytest.raises(HTTPException) as exc_info:
            auth_service.check_entity_owned_by_user(user, None)
        assert exc_info.value.status_code == 404
        assert "Entity does not exist" in exc_info.value.detail

    def test_check_entity_owned_by_user_wrong_owner(self, auth_service):
        """Test check_entity_owned_by_user when entity belongs to different user."""
        user = User(id=uuid4(), email="user@example.com", password="hash", is_active=True, last_login_at=None, created_at=datetime.now(UTC))
        other_id = uuid4()

        class MockEntity:
            user_id = other_id

        entity = MockEntity()
        with pytest.raises(HTTPException) as exc_info:
            auth_service.check_entity_owned_by_user(user, entity)
        assert exc_info.value.status_code == 404
        assert "Entity does not exist" in exc_info.value.detail

    def test_check_entity_owned_by_user_custom_field(self, auth_service):
        """Test check_entity_owned_by_user with custom field name."""
        user = User(id=uuid4(), email="user@example.com", password="hash", is_active=True, last_login_at=None, created_at=datetime.now(UTC))

        class MockEntity:
            owner_id = user.id

        entity = MockEntity()
        auth_service.check_entity_owned_by_user(user, entity, field="owner_id")

    def test_check_entity_owned_by_user_custom_field_fail(self, auth_service):
        """Test check_entity_owned_by_user with custom field when not matching."""
        user = User(id=uuid4(), email="user@example.com", password="hash", is_active=True, last_login_at=None, created_at=datetime.now(UTC))

        class MockEntity:
            owner_id = uuid4()  # Different

        entity = MockEntity()
        with pytest.raises(HTTPException) as exc_info:
            auth_service.check_entity_owned_by_user(user, entity, field="owner_id")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_check_entity_owned_by_user_from_token_success(self, auth_service, mock_user_service):
        """Test check_entity_owned_by_user_from_token success."""
        token = "valid_token"
        user = User(id=uuid4(), email="user@example.com", password="hash", is_active=True, last_login_at=None, created_at=datetime.now(UTC))
        mock_user_service.get_current_user_from_token = AsyncMock(return_value=user)

        class MockEntity:
            user_id = user.id

        entity = MockEntity()
        await auth_service.check_entity_owned_by_user_from_token(token, entity)
        mock_user_service.get_current_user_from_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_check_entity_owned_by_user_from_token_none_entity(self, auth_service, mock_user_service):
        """Test check_entity_owned_by_user_from_token with None entity."""
        token = "valid_token"
        user = User(id=uuid4(), email="user@example.com", password="hash", is_active=True, last_login_at=None, created_at=datetime.now(UTC))
        mock_user_service.get_current_user_from_token = AsyncMock(return_value=user)

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.check_entity_owned_by_user_from_token(token, None)
        assert exc_info.value.status_code == 404
        mock_user_service.get_current_user_from_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_check_entity_owned_by_user_from_token_wrong_owner(self, auth_service, mock_user_service):
        """Test check_entity_owned_by_user_from_token when not owner."""
        token = "valid_token"
        user = User(id=uuid4(), email="user@example.com", password="hash", is_active=True, last_login_at=None, created_at=datetime.now(UTC))
        mock_user_service.get_current_user_from_token = AsyncMock(return_value=user)

        class MockEntity:
            user_id = uuid4()  # Different

        entity = MockEntity()
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.check_entity_owned_by_user_from_token(token, entity)
        assert exc_info.value.status_code == 404
        mock_user_service.get_current_user_from_token.assert_called_once_with(token)
