"""Tests for UserApi facade methods."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.auth.api import UserApi
from src.auth.api_types import UserId
from src.auth.repository import UserRepository
from src.auth.schema import UserSchema
from src.auth.service import EmailVerificationService


class MockUserRepository(UserRepository):
    """Minimal in-memory UserRepository for UserApi facade tests."""

    def __init__(self, users: dict[UserId, UserSchema] | None = None) -> None:
        self._users = users or {}

    async def get_by_id(self, user_id: UserId) -> UserSchema | None:
        return self._users.get(user_id)

    async def get_by_email(self, _email: str) -> UserSchema | None:
        return None

    async def create_user(self, email: str, plain_text_password: str) -> UserSchema:
        raise NotImplementedError

    async def mark_as_verified(self, user_id: UserId) -> None: ...


class TestGetEmailForUser:
    @pytest.mark.asyncio
    async def test_returns_email_when_user_exists(self):
        """get_email_for_user returns the user's email when found."""
        user_id = uuid4()
        user = UserSchema(
            id=user_id,
            email="trader@example.com",
            password="hashed_password",  # noqa: S106
            is_verified=True,
            created_at=__import__("datetime").datetime.now(),
        )
        user_repo = MockUserRepository({user_id: user})
        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        email = await api.get_email_for_user(user_id)
        assert email == "trader@example.com"

    @pytest.mark.asyncio
    async def test_returns_none_when_user_not_found(self):
        """get_email_for_user returns None for a non-existent user."""
        user_repo = MockUserRepository()
        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        email = await api.get_email_for_user(uuid4())
        assert email is None
