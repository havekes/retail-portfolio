from datetime import datetime

from argon2 import PasswordHasher
from pydantic import BaseModel, ConfigDict, EmailStr

from src.auth.api_types import UserId

_password_hasher = PasswordHasher()


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UserId
    email: str
    password: str  # hashed
    is_active: bool = True
    is_verified: bool = False
    last_login_at: datetime | None = None
    created_at: datetime

    def verify_password(self, plain_text_password: str) -> bool:
        """Verifies the password against the stored hash."""
        try:
            return _password_hasher.verify(self.password, plain_text_password)
        except Exception:  # noqa: BLE001
            return False


class VerificationTokenSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: UserId
    token: str
    expires_at: datetime
    is_used: bool = False
    created_at: datetime


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str
