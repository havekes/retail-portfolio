from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.auth.api_types import UserId
from src.config.database import BaseModel

_password_hasher = PasswordHasher()


class UserModel(BaseModel):
    """User model."""

    __tablename__ = "auth_users"

    id: Mapped[UserId] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    _password_hash: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    @property
    def password(self):
        """Prevents the password hash from being read directly."""
        return self._password_hash

    @password.setter
    def password(self, value: str):
        """Hashes the password automatically when assigned."""
        self._password_hash = _password_hasher.hash(value)

    def check_password(self, plain_text_password: str) -> bool:
        """Verifies the password against the stored hash."""
        try:
            return _password_hasher.verify(self._password_hash, plain_text_password)
        except Exception:  # noqa: BLE001
            return False


class VerificationTokenModel(BaseModel):
    """Email verification token model."""

    __tablename__ = "auth_verification_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Usually UUID string
    user_id: Mapped[UserId] = mapped_column(Uuid, index=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )


class TotpModel(BaseModel):
    """TOTP two-factor authentication credentials model."""

    __tablename__ = "auth_totp"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UserId] = mapped_column(
        Uuid,
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    secret: Mapped[str] = mapped_column(String)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )


class RecoveryCodeModel(BaseModel):
    """Backup recovery codes model."""

    __tablename__ = "auth_recovery_codes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UserId] = mapped_column(
        Uuid,
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )


class PasskeyModel(BaseModel):
    """WebAuthn passkey credential model."""

    __tablename__ = "auth_passkeys"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UserId] = mapped_column(
        Uuid,
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        index=True,
    )
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, unique=True, index=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String)
    transports: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
