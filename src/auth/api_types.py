from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

type UserId = UUID

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


class User(BaseModel):
    id: UserId
    email: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH or len(v) > MAX_PASSWORD_LENGTH:
            msg = (
                f"Password must be between {MIN_PASSWORD_LENGTH} and "
                f"{MAX_PASSWORD_LENGTH} characters"
            )
            raise ValueError(msg)
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) > MAX_PASSWORD_LENGTH:
            msg = f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters"
            raise ValueError(msg)
        return v


class SignupResponse(BaseModel):
    message: str


class AuthResponse(BaseModel):
    access_token: str
    user: User


class AccessTokenData(BaseModel):
    sub: str
    user_id: str
    exp: int
    scope: str = "access"
    jti: str = ""
