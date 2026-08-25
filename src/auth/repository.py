from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.auth.api_types import UserId
from src.auth.schema import (
    PasskeySchema,
    RecoveryCodeSchema,
    TotpSchema,
    UserSchema,
    VerificationTokenSchema,
)


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

    @abstractmethod
    async def get_preferences(self, user_id: UserId) -> dict | None:
        pass

    @abstractmethod
    async def save_preferences(self, user_id: UserId, preferences: dict) -> None:
        pass

    @abstractmethod
    async def patch_preferences(self, user_id: UserId, preferences: dict) -> dict:
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


class TotpRepository(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: UserId) -> TotpSchema | None:
        pass

    @abstractmethod
    async def create_or_update(self, user_id: UserId, secret: str) -> TotpSchema:
        pass

    @abstractmethod
    async def mark_as_verified(self, user_id: UserId) -> None:
        pass

    @abstractmethod
    async def delete_by_user_id(self, user_id: UserId) -> None:
        pass


class RecoveryCodeRepository(ABC):
    @abstractmethod
    async def create_recovery_codes(
        self, user_id: UserId, code_hashes: list[str]
    ) -> list[RecoveryCodeSchema]:
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: UserId) -> list[RecoveryCodeSchema]:
        pass

    @abstractmethod
    async def get_active_by_user_id(self, user_id: UserId) -> list[RecoveryCodeSchema]:
        pass

    @abstractmethod
    async def mark_as_used(self, code_id: UUID) -> None:
        pass

    @abstractmethod
    async def count_active_by_user_id(self, user_id: UserId) -> int:
        pass

    @abstractmethod
    async def delete_by_user_id(self, user_id: UserId) -> None:
        pass


class PasskeyRepository(ABC):
    @abstractmethod
    async def create_passkey(  # noqa: PLR0913
        self,
        user_id: UserId,
        *,
        credential_id: bytes,
        public_key: bytes,
        sign_count: int = 0,
        name: str = "Passkey",
        transports: list[str] | None = None,
    ) -> PasskeySchema:
        pass

    @abstractmethod
    async def get_by_id(self, passkey_id: UUID) -> PasskeySchema | None:
        pass

    @abstractmethod
    async def get_by_credential_id(self, credential_id: bytes) -> PasskeySchema | None:
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: UserId) -> list[PasskeySchema]:
        pass

    @abstractmethod
    async def update_name(self, passkey_id: UUID, name: str) -> PasskeySchema | None:
        pass

    @abstractmethod
    async def update_sign_count_and_last_used(
        self, passkey_id: UUID, sign_count: int, last_used_at: datetime | None = None
    ) -> None:
        pass

    @abstractmethod
    async def delete_by_id(self, passkey_id: UUID, user_id: UserId) -> bool:
        pass
