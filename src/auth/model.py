from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from argon2 import PasswordHasher
from sqlalchemy import Boolean, DateTime, String, Uuid, func
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
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
