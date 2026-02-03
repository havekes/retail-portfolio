from uuid import UUID

from pydantic import BaseModel, EmailStr

type UserId = UUID


class User(BaseModel):
    id: UserId
    email: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user: User


class AccessTokenData(BaseModel):
    sub: str
    exp: int
