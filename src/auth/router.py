import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import URLSafeTimedSerializer
from pydantic import BaseModel
from svcs.fastapi import DepContainer

from src.auth.api import UserApi, current_user
from src.auth.api_types import (
    AuthResponse,
    LoginRequest,
    SignupRequest,
    SignupResponse,
    User,
)
from src.auth.exception import (
    AuthInvalidCredentialsError,
    AuthUserAlreadyExistsError,
    AuthUserUnverifiedError,
)
from src.auth.schema import (
    MessageResponse,
    ResendVerificationRequest,
    TotpActivateRequest,
    TotpActivateResponse,
    TotpDisableRequest,
    TotpRegenerateCodesResponse,
    TotpSetupResponse,
    TwoFactorStatusResponse,
    VerifyEmailRequest,
)
from src.auth.service import TotpService
from src.config.limiter import limiter
from src.config.settings import settings
from src.core.email import EmailSendError

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth")


@auth_router.post("/signup")
@limiter.limit("5/minute")
async def auth_signup(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    signup_data: SignupRequest,
    services: DepContainer,
) -> SignupResponse:
    user_service = await services.aget(UserApi)
    try:
        return await user_service.signup(signup_data.email, signup_data.password)
    except AuthUserAlreadyExistsError as e:
        raise HTTPException(409, "User with email already exists") from e
    except EmailSendError as e:
        raise HTTPException(
            502,
            "Account created but verification email failed to send."
            "Please use resend-verification to try again.",
        ) from e


@auth_router.post("/login")
@limiter.limit("10/minute")
async def auth_login(
    request: Request,  # noqa: ARG001
    response: Response,
    login_data: LoginRequest,
    services: DepContainer,
) -> AuthResponse:
    user_service = await services.aget(UserApi)
    try:
        auth_data = await user_service.login(login_data.email, login_data.password)
    except AuthInvalidCredentialsError as e:
        logger.warning("Login failed for %s: Invalid credentials", login_data.email)
        raise HTTPException(401, "Invalid credentials") from e
    except AuthUserUnverifiedError as e:
        logger.warning("Login failed for %s: Email not verified", login_data.email)
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
@limiter.limit("3/minute")
async def auth_resend_verification(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    resend_data: ResendVerificationRequest,
    services: DepContainer,
) -> MessageResponse:
    user_service = await services.aget(UserApi)
    try:
        await user_service.resend_verification(resend_data.email)
    except EmailSendError as e:
        raise HTTPException(
            502,
            "Failed to send verification email. Please try again later.",
        ) from e
    return MessageResponse(
        message="Verification email sent if user exists and is unverified"
    )


@auth_router.post("/ws-ticket")
async def auth_ws_ticket(
    services: DepContainer,
    token: str = Cookie(default=None, alias="auth_token"),
) -> JSONResponse:
    if not token:
        raise HTTPException(401, "Not authenticated")

    user_service = await services.aget(UserApi)
    user = await user_service.get_current_user_from_token(token)

    serializer = URLSafeTimedSerializer(settings.secret_key)
    payload = json.dumps({"user_id": str(user.id), "jti": str(uuid.uuid4())})
    ticket = serializer.dumps(payload, salt="ws-ticket")

    return JSONResponse({"ticket": ticket})


@auth_router.get("/2fa/status")
async def auth_2fa_status(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> TwoFactorStatusResponse:
    totp_service = await services.aget(TotpService)
    return await totp_service.get_2fa_status(user.id)


@auth_router.post("/2fa/totp/setup")
async def auth_totp_setup(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> TotpSetupResponse:
    totp_service = await services.aget(TotpService)
    return await totp_service.setup_totp(user.id, user.email)


@auth_router.post("/2fa/totp/activate")
async def auth_totp_activate(
    request: TotpActivateRequest,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> TotpActivateResponse:
    totp_service = await services.aget(TotpService)
    return await totp_service.activate_totp(user.id, request.code)


@auth_router.post("/2fa/totp/disable")
async def auth_totp_disable(
    request: TotpDisableRequest,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> MessageResponse:
    totp_service = await services.aget(TotpService)
    await totp_service.disable_totp(
        user.id, code=request.code, password=request.password
    )
    return MessageResponse(
        message="TOTP two-factor authentication disabled successfully"
    )


@auth_router.post("/2fa/totp/recovery-codes/regenerate")
async def auth_totp_regenerate_recovery_codes(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> TotpRegenerateCodesResponse:
    totp_service = await services.aget(TotpService)
    return await totp_service.regenerate_recovery_codes(user.id)
