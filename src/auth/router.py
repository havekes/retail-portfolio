from typing import Annotated

from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException
from svcs.fastapi import DepContainer

from src.auth.api import UserApi
from src.auth.api_types import AuthResponse, LoginRequest, SignupRequest, SignupResponse
from src.auth.exceptions import (
    AuthInvalidCredentialsError,
    AuthUserAlreadyExistsError,
    AuthUserUnverifiedError,
)

auth_router = APIRouter(prefix="/api/auth")


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str


@auth_router.post("/signup", response_model=SignupResponse)
async def signup(
    request: SignupRequest,
    services: DepContainer,
) -> SignupResponse:
    user_service = await services.aget(UserApi)
    try:
        return await user_service.signup(request.email, request.password)
    except AuthUserAlreadyExistsError as e:
        raise HTTPException(409, "User with email already exists") from e


@auth_router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    services: DepContainer,
) -> AuthResponse:
    user_service = await services.aget(UserApi)
    try:
        return await user_service.login(request.email, request.password)
    except AuthInvalidCredentialsError as e:
        raise HTTPException(401, "Invalid credentials") from e
    except AuthUserUnverifiedError as e:
        raise HTTPException(403, "Email not verified") from e


@auth_router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    request: VerifyEmailRequest,
    services: DepContainer,
) -> MessageResponse:
    user_service = await services.aget(UserApi)
    await user_service.verify_email(request.token)
    return MessageResponse(message="Email verified successfully")


@auth_router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    request: ResendVerificationRequest,
    services: DepContainer,
) -> MessageResponse:
    user_service = await services.aget(UserApi)
    await user_service.resend_verification(request.email)
    return MessageResponse(message="Verification email sent if user exists and is unverified")
