from typing import Annotated

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from svcs.fastapi import DepContainer

from src.auth.api import UserApi
from src.auth.api_types import AuthResponse, LoginRequest, SignupRequest, SignupResponse
from src.auth.exceptions import (
    AuthInvalidCredentialsError,
    AuthUserAlreadyExistsError,
    AuthUserUnverifiedError,
)
from src.auth.schema import (
    MessageResponse,
    ResendVerificationRequest,
    VerifyEmailRequest,
)
from src.config.settings import settings
from src.core.email import EmailSendError

auth_router = APIRouter(prefix="/api/auth")


@auth_router.post("/signup")
async def auth_signup(
    request: SignupRequest,
    services: DepContainer,
) -> SignupResponse:
    user_service = await services.aget(UserApi)
    try:
        return await user_service.signup(request.email, request.password)
    except AuthUserAlreadyExistsError as e:
        raise HTTPException(409, "User with email already exists") from e
    except EmailSendError as e:
        raise HTTPException(
            502,
            "Account created but verification email failed to send."
            "Please use resend-verification to try again.",
        ) from e


@auth_router.post("/login")
async def auth_login(
    request: LoginRequest,
    services: DepContainer,
    response: Response,
) -> AuthResponse:
    user_service = await services.aget(UserApi)
    try:
        auth_data = await user_service.login(request.email, request.password)
    except AuthInvalidCredentialsError as e:
        raise HTTPException(401, "Invalid credentials") from e
    except AuthUserUnverifiedError as e:
        raise HTTPException(403, "Email not verified") from e
    else:
        response.set_cookie(
            key="auth_token",
            value=auth_data.access_token,
            httponly=settings.environment == "prod",
            secure=settings.environment == "prod",
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days
        )
        return auth_data


@auth_router.post("/logout")
async def auth_logout(
    response: Response,
) -> MessageResponse:
    response.delete_cookie(
        key="auth_token",
        httponly=settings.environment == "prod",
        secure=settings.environment == "prod",
        samesite="lax",
    )
    return MessageResponse(message="Logged out successfully")


@auth_router.post("/verify-email")
async def auth_verify_email(
    request: VerifyEmailRequest,
    services: DepContainer,
) -> MessageResponse:
    user_service = await services.aget(UserApi)
    await user_service.verify_email(request.token)
    return MessageResponse(message="Email verified successfully")


@auth_router.post("/resend-verification")
async def auth_resend_verification(
    request: ResendVerificationRequest,
    services: DepContainer,
) -> MessageResponse:
    user_service = await services.aget(UserApi)
    try:
        await user_service.resend_verification(request.email)
    except EmailSendError as e:
        raise HTTPException(
            502,
            "Failed to send verification email. Please try again later.",
        ) from e
    return MessageResponse(
        message="Verification email sent if user exists and is unverified"
    )
