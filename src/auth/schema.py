from datetime import datetime
from uuid import UUID

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
    preferences: dict | None = None
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


class TotpSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UserId
    secret: str
    is_verified: bool
    created_at: datetime


class RecoveryCodeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UserId
    code_hash: str
    is_used: bool
    used_at: datetime | None = None
    created_at: datetime


class TwoFactorStatusResponse(BaseModel):
    totp_enabled: bool
    recovery_codes_remaining: int


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TotpActivateRequest(BaseModel):
    code: str


class TotpActivateResponse(BaseModel):
    recovery_codes: list[str]
    message: str = "TOTP two-factor authentication enabled successfully"


class TotpDisableRequest(BaseModel):
    code: str | None = None
    password: str | None = None


class TotpRegenerateCodesResponse(BaseModel):
    recovery_codes: list[str]


class LoginChallengeResponse(BaseModel):
    requires_2fa: bool = True
    mfa_token: str


class LoginVerifyRequest(BaseModel):
    mfa_token: str
    code: str
