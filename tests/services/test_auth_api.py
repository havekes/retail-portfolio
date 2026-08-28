"""Tests for UserApi facade methods."""

import contextlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from argon2 import PasswordHasher
from fastapi import HTTPException

from src.auth.api import UserApi
from src.auth.api_types import AuthResponse, UserId
from src.auth.exception import AuthInvalidCredentialsError
from src.auth.repository import TotpRepository, UserRepository
from src.auth.schema import LoginChallengeResponse, TotpSchema, UserSchema
from src.auth.service import EmailVerificationService
from src.core.redis import RedisManager


class MockUserRepository(UserRepository):
    """Minimal in-memory UserRepository for UserApi facade tests."""

    def __init__(
        self,
        users: dict[UserId, UserSchema] | None = None,
        prefs: dict[UserId, dict] | None = None,
    ) -> None:
        self._users = users or {}
        self._prefs = prefs or {}

    async def get_by_id(self, user_id: UserId) -> UserSchema | None:
        return self._users.get(user_id)

    async def get_by_email(self, email: str) -> UserSchema | None:  # noqa: ARG002
        return None

    async def create_user(self, email: str, plain_text_password: str) -> UserSchema:
        raise NotImplementedError

    async def mark_as_verified(self, user_id: UserId) -> None: ...

    async def update_last_login(self, user_id: UserId) -> None:
        user = self._users.get(user_id)
        if user:
            user.last_login_at = datetime.now(UTC)

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
        payload = {
            "timeframe": "1d",
            "chart_style": "candlestick",
            "indicators": {"rsi": {"enabled": True}},
        }
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
        assert res == {
            "timeframe": "4h",
            "chart_style": "candlestick",
            "sidebar_open": False,
        }
        assert await api.get_preferences(user_id) == res


class MockTotpRepository(TotpRepository):
    """Minimal in-memory TotpRepository for UserApi tests."""

    def __init__(self, totps: dict[UserId, TotpSchema] | None = None) -> None:
        self.totps = totps or {}

    async def get_by_user_id(self, user_id: UserId) -> TotpSchema | None:
        return self.totps.get(user_id)

    async def create_or_update(self, user_id: UserId, secret: str) -> TotpSchema:
        raise NotImplementedError

    async def mark_as_verified(self, user_id: UserId) -> None:
        raise NotImplementedError

    async def delete_by_user_id(self, user_id: UserId) -> None:
        raise NotImplementedError


class TestMfaTokens:
    def test_create_and_verify_mfa_token(self):
        """create_mfa_token issues a token with scope='mfa_pending' decodable by verify_mfa_token."""
        user_id = uuid4()
        api = UserApi(
            user_repository=MockUserRepository(),
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        token = api.create_mfa_token("user@example.com", user_id)
        token_data = api.verify_mfa_token(token)

        assert token_data.sub == "user@example.com"
        assert token_data.user_id == str(user_id)
        assert token_data.scope == "mfa_pending"

    def test_verify_mfa_token_rejects_access_token(self):
        """verify_mfa_token rejects standard access tokens with 401."""
        user_id = uuid4()
        api = UserApi(
            user_repository=MockUserRepository(),
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        access_token = api.create_access_token("user@example.com", user_id)

        with pytest.raises(HTTPException) as exc:
            api.verify_mfa_token(access_token)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_rejects_mfa_token(self):
        """get_current_user_from_token rejects mfa_pending tokens with 401 Token invalid."""
        user_id = uuid4()
        user = UserSchema(
            id=user_id,
            email="user@example.com",
            password="hashed_password",  # noqa: S106
            is_verified=True,
            created_at=datetime.now(UTC),
        )
        user_repo = MockUserRepository({user_id: user})
        # Override get_by_email for this test
        user_repo.get_by_email = AsyncMock(return_value=user)  # type: ignore[method-assign]
        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )

        mfa_token = api.create_mfa_token("user@example.com", user_id)

        with pytest.raises(HTTPException) as exc:
            await api.get_current_user_from_token(mfa_token)
        assert exc.value.status_code == 401
        assert exc.value.detail == "Token invalid"


class TestLogin2faChallenge:
    @pytest.mark.asyncio
    async def test_login_returns_challenge_when_2fa_enabled(self):
        """login returns LoginChallengeResponse when TOTP is verified for the user."""
        user_id = uuid4()
        from argon2 import PasswordHasher

        hasher = PasswordHasher()
        user = UserSchema(
            id=user_id,
            email="2fa_user@example.com",
            password=hasher.hash("secret_password"),  # noqa: S106
            is_verified=True,
            created_at=datetime.now(UTC),
        )
        totp_schema = TotpSchema(
            id=uuid4(),
            user_id=user_id,
            secret="JBSWY3DPEHPK3PXP",
            is_verified=True,
            created_at=datetime.now(UTC),
        )
        user_repo = MockUserRepository({user_id: user})
        user_repo.get_by_email = AsyncMock(return_value=user)  # type: ignore[method-assign]
        totp_repo = MockTotpRepository({user_id: totp_schema})

        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
            totp_repository=totp_repo,
        )

        response = await api.login("2fa_user@example.com", "secret_password")
        assert isinstance(response, LoginChallengeResponse)
        assert response.requires_2fa is True
        assert response.mfa_token is not None

    @pytest.mark.asyncio
    async def test_login_returns_auth_response_when_2fa_disabled(self):
        """login returns standard AuthResponse when TOTP is not configured/verified."""
        user_id = uuid4()
        from argon2 import PasswordHasher

        hasher = PasswordHasher()
        user = UserSchema(
            id=user_id,
            email="standard_user@example.com",
            password=hasher.hash("secret_password"),  # noqa: S106
            is_verified=True,
            created_at=datetime.now(UTC),
        )
        user_repo = MockUserRepository({user_id: user})
        user_repo.get_by_email = AsyncMock(return_value=user)  # type: ignore[method-assign]
        totp_repo = MockTotpRepository()  # no totp record

        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
            totp_repository=totp_repo,
        )

        response = await api.login("standard_user@example.com", "secret_password")
        assert isinstance(response, AuthResponse)
        assert response.access_token is not None
        assert response.user.id == user_id


class TestGetUserById:
    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self):
        user_id = uuid4()
        user = UserSchema(
            id=user_id,
            email="user@example.com",
            password="hashed_password",  # noqa: S106
            is_verified=True,
            created_at=datetime.now(UTC),
        )
        user_repo = MockUserRepository({user_id: user})
        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        found = await api.get_user_by_id(user_id)
        assert found is not None
        assert found.id == user_id

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self):
        user_repo = MockUserRepository()
        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        found = await api.get_user_by_id(uuid4())
        assert found is None


class TestLoginEnumeration:
    @pytest.mark.asyncio
    async def test_unknown_email_returns_same_error_as_wrong_password(self):
        """Unknown email and wrong password both raise AuthInvalidCredentialsError."""
        user_id = uuid4()
        hasher = PasswordHasher()
        user = UserSchema(
            id=user_id,
            email="known_user@example.com",
            password=hasher.hash("correct_password"),  # noqa: S106
            is_verified=True,
            created_at=datetime.now(UTC),
        )
        user_repo = MockUserRepository({user_id: user})
        user_repo.get_by_email = AsyncMock(  # type: ignore[method-assign]
            side_effect=lambda email: (
                user if email == "known_user@example.com" else None
            )
        )

        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )

        # Unknown email raises AuthInvalidCredentialsError
        with pytest.raises(AuthInvalidCredentialsError):
            await api.login("unknown_user@example.com", "any_password")

        # Wrong password for existing user raises the same AuthInvalidCredentialsError
        with pytest.raises(AuthInvalidCredentialsError):
            await api.login("known_user@example.com", "wrong_password")


class FakeRedisClient:
    def __init__(self, storage: dict[str, str]):
        self.storage = storage

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def setex(self, key: str, time: int, value: str) -> None:  # noqa: ARG002
        self.storage[key] = value


class FakeRedisManager(RedisManager):
    def __init__(self, storage: dict[str, str] | None = None):
        self.storage = storage if storage is not None else {}

    @contextlib.asynccontextmanager
    async def client(self):
        yield FakeRedisClient(self.storage)


class TestTokenRevocation:
    @pytest.mark.asyncio
    async def test_revoked_token_rejected(self):
        """get_current_user_from_token raises 401 'Token revoked' when jti is denylisted."""
        user_id = uuid4()
        user = UserSchema(
            id=user_id,
            email="revoked@example.com",
            password="hashed_password",  # noqa: S106
            is_verified=True,
            created_at=datetime.now(UTC),
        )
        user_repo = MockUserRepository({user_id: user})
        user_repo.get_by_email = AsyncMock(return_value=user)  # type: ignore[method-assign]
        fake_redis = FakeRedisManager()

        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
            redis_manager=fake_redis,
        )

        token = api.create_access_token("revoked@example.com", user_id)

        # Before revocation: valid token resolves to user
        resolved_user = await api.get_current_user_from_token(token)
        assert resolved_user.id == user_id

        # Revoke the token
        await api.revoke_token(token)

        # After revocation: raises 401 Token revoked
        with pytest.raises(HTTPException) as exc_info:
            await api.get_current_user_from_token(token)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Token revoked"

    @pytest.mark.asyncio
    async def test_revoke_invalid_token_silently_ignored(self):
        """revoke_token gracefully ignores invalid/malformed tokens."""
        fake_redis = FakeRedisManager()
        api = UserApi(
            user_repository=MockUserRepository(),
            email_verification_service=AsyncMock(spec=EmailVerificationService),
            redis_manager=fake_redis,
        )
        await api.revoke_token("not-a-valid-token")
        assert len(fake_redis.storage) == 0

    @pytest.mark.asyncio
    async def test_revoke_expired_token_silently_ignored(self):
        """revoke_token gracefully ignores already expired tokens."""
        user_id = uuid4()
        fake_redis = FakeRedisManager()
        api = UserApi(
            user_repository=MockUserRepository(),
            email_verification_service=AsyncMock(spec=EmailVerificationService),
            redis_manager=fake_redis,
        )
        expired_token = api.create_access_token(
            "test@example.com", user_id, expires_delta=timedelta(seconds=-10)
        )
        await api.revoke_token(expired_token)
        assert len(fake_redis.storage) == 0


class TestUpdateLastLogin:
    @pytest.mark.asyncio
    async def test_update_last_login_delegates_to_repo(self):
        user_id = uuid4()
        user = UserSchema(
            id=user_id,
            email="login_user@example.com",
            password="hashed_password",  # noqa: S106
            is_verified=True,
            created_at=datetime.now(UTC),
        )
        user_repo = MockUserRepository({user_id: user})
        api = UserApi(
            user_repository=user_repo,
            email_verification_service=AsyncMock(spec=EmailVerificationService),
        )
        assert user.last_login_at is None
        await api.update_last_login(user_id)
        assert user.last_login_at is not None
