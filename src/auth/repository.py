from abc import ABC, abstractmethod
from datetime import datetime

from src.auth.api_types import UserId
from src.auth.schema import UserSchema, VerificationTokenSchema


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UserId) -> UserSchema | None:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> UserSchema | None:
        pass

    @abstractmethod
    async def create_user(self, email: str, plain_text_password: str) -> UserSchema:
        pass

    @abstractmethod
    async def mark_as_verified(self, user_id: UserId) -> None:
        pass


class VerificationTokenRepository(ABC):
    @abstractmethod
    async def create_token(
        self, user_id: UserId, token: str, expires_at: datetime
    ) -> VerificationTokenSchema:
        pass

    @abstractmethod
    async def get_by_token(self, token: str) -> VerificationTokenSchema | None:
        pass

    @abstractmethod
    async def get_by_user(self, user_id: UserId) -> VerificationTokenSchema | None:
        pass

    @abstractmethod
    async def mark_as_used(self, token_id: str) -> None:
        pass

    @abstractmethod
    async def invalidate_tokens_for_user(self, user_id: UserId) -> None:
        pass
