from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from svcs import Container

from src.config.settings import settings
from src.repositories.user import UserRepository
from src.schemas.auth import AccessTokenData, AuthResponse
from src.services.exceptions import (
    AuthInvalidCredentialsError,
    AuthUserAlreadyExistsError,
)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class AuthService:
    _user_repository: UserRepository

    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def hash_password(self, password: str) -> str:
        password_bytes = password.encode("utf-8")[:72]
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

        return hashed.decode("utf-8")

    def create_access_token(
        self, user_email: str, expires_delta: timedelta | None = None
    ):
        access_token_data = AccessTokenData(
            sub=user_email,
            exp=str(
                datetime.now(UTC)
                + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
            ),
        )

        return jwt.encode(
            access_token_data.model_dump(),
            settings.secret_key,
            algorithm=ALGORITHM,
        )

    async def signup(self, email: str, password: str) -> AuthResponse:
        existing_user = await self._user_repository.get_by_email(email)

        if existing_user is not None:
            raise AuthUserAlreadyExistsError

        hashed_password = self.hash_password(password)
        user = await self._user_repository.create_user(email, hashed_password)
        access_token = self.create_access_token(user.email)

        return AuthResponse(access_token=access_token, user=user)

    async def login(self, email: str, password: str) -> AuthResponse:
        user = await self._user_repository.get_by_email(email)

        if not user or not self.verify_password(password, user.password):
            raise AuthInvalidCredentialsError

        access_token = self.create_access_token(user.email)

        return AuthResponse(access_token=access_token, user=user)


async def auth_service_factory(
    container: Container,
) -> AsyncGenerator[AuthService]:
    yield AuthService(
        user_repository=await container.aget(UserRepository),
    )
