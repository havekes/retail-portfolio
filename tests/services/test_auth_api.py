"""Tests for UserApi facade methods."""

from datetime import UTC, datetime
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

    def __init__(self, users: dict[UserId, UserSchema] | None = None, prefs: dict[UserId, dict] | None = None) -> None:
        self._users = users or {}
        self._prefs = prefs or {}

    async def get_by_id(self, user_id: UserId) -> UserSchema | None:
        return self._users.get(user_id)

    async def get_by_email(self, email: str) -> UserSchema | None:  # noqa: ARG002
        return None

    async def create_user(self, email: str, plain_text_password: str) -> UserSchema:
        raise NotImplementedError

    async def mark_as_verified(self, user_id: UserId) -> None: ...

    async def get_preferences(self, user_id: UserId) -> dict | None:
        return self._prefs.get(user_id)

    async def save_preferences(self, user_id: UserId, preferences: dict) -> None:
        self._prefs[user_id] = preferences

    async def patch_preferences(self, user_id: UserId, preferences: dict) -> dict:
        current = self._prefs.get(user_id) or {}
        updated = {**current, **preferences}
        self._prefs[user_id] = updated
        return updated


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
            created_at=datetime.now(UTC),
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


class TestPreferences:
    @pytest.mark.asyncio
    async def test_get_preferences_returns_none_when_not_saved(self):
        """get_preferences returns None when no preferences saved."""
        user_id = uuid4()
        user_repo = MockUserRepository()
        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        prefs = await api.get_preferences(user_id)
        assert prefs is None

    @pytest.mark.asyncio
    async def test_save_then_get_preferences_roundtrip(self):
        """Save preferences then retrieve — round-trip through the facade."""
        user_id = uuid4()
        payload = {"timeframe": "1d", "chart_style": "candlestick", "indicators": {"rsi": {"enabled": True}}}
        user_repo = MockUserRepository()
        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        await api.save_preferences(user_id, payload)
        prefs = await api.get_preferences(user_id)
        assert prefs == payload

    @pytest.mark.asyncio
    async def test_patch_preferences_updates_and_returns_merged_dict(self):
        """Patch preferences merges with existing and returns the updated preferences."""
        user_id = uuid4()
        initial = {"timeframe": "1d", "chart_style": "candlestick"}
        user_repo = MockUserRepository(prefs={user_id: initial})
        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        patch = {"sidebar_open": False, "timeframe": "4h"}
        res = await api.patch_preferences(user_id, patch)
        assert res == {"timeframe": "4h", "chart_style": "candlestick", "sidebar_open": False}
        assert await api.get_preferences(user_id) == res
