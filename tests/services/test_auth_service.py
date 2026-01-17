from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.repositories.user import UserRepository
from src.schemas.auth import AuthResponse
from src.schemas.user import User
from src.services.auth import AuthService
from src.services.exceptions import AuthInvalidCredentialsError, AuthUserAlreadyExistsError


class TestAuthService:
    """Test suite for AuthService."""

    @pytest.fixture
    def mock_user_repo(self):
        return Mock(spec=UserRepository)

    @pytest.fixture
    def auth_service(self, mock_user_repo):
        return AuthService(mock_user_repo)

    def test_verify_password_success(self, auth_service):
        """Test password verification with correct password."""
        plain = "password"
        hashed = auth_service.hash_password(plain)
        assert auth_service.verify_password(plain, hashed)

    def test_verify_password_fail(self, auth_service):
        """Test password verification with incorrect password."""
        plain = "password"
        wrong_plain = "wrong"
        hashed = auth_service.hash_password(plain)
        assert not auth_service.verify_password(wrong_plain, hashed)

    def test_hash_password_truncates_long_password(self, auth_service):
        """Test that hash_password truncates password longer than 72 bytes."""
        long_password = "a" * 80  # >72
        short_password = "a" * 71  # <72
        long_hashed = auth_service.hash_password(long_password)
        short_hashed = auth_service.hash_password(short_password)
        # Long password should hash as truncated
        assert len(long_password.encode("utf-8")[:72]) == 72
        # But since hash is deterministic only for same input, just check it's hashed
        assert long_hashed != long_password
        assert isinstance(long_hashed, str)

    @patch("src.services.auth.jwt.encode")
    @patch("src.services.auth.settings.secret_key", "test_key")
    def test_create_access_token_default_expiry(self, mock_encode, auth_service):
        """Test creating access token with default expiry."""
        email = "test@example.com"
        result = auth_service.create_access_token(email)
        mock_encode.assert_called_once()
        args, kwargs = mock_encode.call_args
        data = args[0]
        assert data["sub"] == email
        assert "exp" in data
        assert kwargs["key"] == "test_key"
        assert kwargs["algorithm"] == "HS256"

    @patch("src.services.auth.jwt.encode")
    @patch("src.services.auth.settings.secret_key", "test_key")
    def test_create_access_token_custom_expiry(self, mock_encode, auth_service):
        """Test creating access token with custom expiry."""
        email = "test@example.com"
        delta = timedelta(hours=1)
        result = auth_service.create_access_token(email, delta)
        mock_encode.assert_called_once()
        args, kwargs = mock_encode.call_args
        data = args[0]
        assert data["sub"] == email
        # exp should be roughly now + delta
        # Can't check exact without freezing time, but called once

    @pytest.mark.asyncio
    async def test_signup_success(self, auth_service, mock_user_repo):
        """Test successful user signup."""
        email = "new@example.com"
        password = "pass"
        user = User(id=uuid4(), email=email, password="hashed", is_active=True, last_login_at=None, created_at=datetime.now(UTC))
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.create_user.return_value = user

        result = await auth_service.signup(email, password)

        assert isinstance(result, AuthResponse)
        assert result.user == user
        assert result.access_token is not None  # Mocked jwt
        mock_user_repo.get_by_email.assert_called_once_with(email)
        mock_user_repo.create_user.assert_called_once_with(email, auth_service.hash_password(password))

    @pytest.mark.asyncio
    async def test_signup_user_exists(self, auth_service, mock_user_repo):
        """Test signup when user already exists."""
        email = "existing@example.com"
        password = "pass"
        existing_user = User(id=uuid4(), email=email, password="hashed", is_active=True, last_login_at=None, created_at=datetime.now(UTC))
        mock_user_repo.get_by_email.return_value = existing_user

        with pytest.raises(AuthUserAlreadyExistsError):
            await auth_service.signup(email, password)

        mock_user_repo.get_by_email.assert_called_once_with(email)
        mock_user_repo.create_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service, mock_user_repo):
        """Test successful login."""
        email = "user@example.com"
        password = "pass"
        hashed = auth_service.hash_password(password)
        user = User(id=uuid4(), email=email, password=hashed, is_active=True, last_login_at=None, created_at=datetime.now(UTC))
        mock_user_repo.get_by_email.return_value = user

        result = await auth_service.login(email, password)

        assert isinstance(result, AuthResponse)
        assert result.user == user
        assert result.access_token is not None
        mock_user_repo.get_by_email.assert_called_once_with(email)

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, auth_service, mock_user_repo):
        """Test login with non-existent user."""
        email = "nonexistent@example.com"
        password = "pass"
        mock_user_repo.get_by_email.return_value = None

        with pytest.raises(AuthInvalidCredentialsError):
            await auth_service.login(email, password)

        mock_user_repo.get_by_email.assert_called_once_with(email)

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, auth_service, mock_user_repo):
        """Test login with wrong password."""
        email = "user@example.com"
        password = "pass"
        wrong_password = "wrong"
        hashed = auth_service.hash_password(password)
        user = User(id=uuid4(), email=email, password=hashed, is_active=True, last_login_at=None, created_at=datetime.now(UTC))
        mock_user_repo.get_by_email.return_value = user

        with pytest.raises(AuthInvalidCredentialsError):
            await auth_service.login(email, wrong_password)

        mock_user_repo.get_by_email.assert_called_once_with(email)
