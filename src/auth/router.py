import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import URLSafeTimedSerializer
from pydantic import BaseModel
from svcs.fastapi import DepContainer

from src.auth.api import UserApi, current_user, oauth2_scheme
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
from src.auth.repository import UserRepository
from src.auth.schema import (
    LoginChallengeResponse,
    LoginVerifyRequest,
    MessageResponse,
    PasskeyAuthenticateOptionsRequest,
    PasskeyAuthenticateVerifyRequest,
    PasskeyRegisterVerifyRequest,
    PasskeyResponse,
    PasskeyUpdateRequest,
    ResendVerificationRequest,
    TotpActivateRequest,
    TotpActivateResponse,
    TotpDisableRequest,
    TotpRegenerateCodesResponse,
    TotpSetupResponse,
    TwoFactorStatusResponse,
    VerifyEmailRequest,
)
from src.auth.service import PasskeyService, TotpService
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
        # Deliberate: 409 informs the user their email is already registered.
        # Unlike resend-verification (silent-success for privacy), signup must
        # explain why the action failed so the user can proceed to login.
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
) -> AuthResponse | LoginChallengeResponse:
    user_service = await services.aget(UserApi)
    user_repo = await services.aget(UserRepository)
    try:
        auth_data = await user_service.login(login_data.email, login_data.password)
    except AuthInvalidCredentialsError as e:
        logger.warning(
            "Login failed for %s: Invalid credentials",
            login_data.email,
            extra={"event": "auth.login_failure", "email": login_data.email},
        )
        raise HTTPException(401, "Invalid credentials") from e
    except AuthUserUnverifiedError as e:
        logger.warning(
            "Login failed for %s: Email not verified",
            login_data.email,
            extra={"event": "auth.login_failure", "email": login_data.email},
        )
        raise HTTPException(403, "Email not verified") from e
    else:
        if isinstance(auth_data, LoginChallengeResponse):
            return auth_data
        response.set_cookie(
            key="auth_token",
            value=auth_data.access_token,
            httponly=settings.environment == "prod",
            secure=settings.environment == "prod",
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days
        )
        await user_repo.update_last_login(auth_data.user.id)
        logger.info(
            "auth.login_success",
            extra={"user_id": str(auth_data.user.id)},
        )
        return auth_data


@auth_router.post("/2fa/login-verify")
@limiter.limit("10/minute")
async def auth_2fa_login_verify(
    request: Request,  # noqa: ARG001
    response: Response,
    verify_data: LoginVerifyRequest,
    services: DepContainer,
) -> AuthResponse:
    user_service = await services.aget(UserApi)
    user_repo = await services.aget(UserRepository)
    totp_service = await services.aget(TotpService)

    token_data = user_service.verify_mfa_token(verify_data.mfa_token)
    try:
        user_id = uuid.UUID(token_data.user_id)
    except ValueError as e:
        raise HTTPException(401, "Token invalid") from e

    user = await user_service.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Token invalid")

    is_valid = await totp_service.verify_2fa_login(user.id, verify_data.code)
    if not is_valid:
        raise HTTPException(401, "Invalid 2FA code")

    access_token = user_service.create_access_token(user.email, user.id)
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=settings.environment == "prod",
        secure=settings.environment == "prod",
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    await user_repo.update_last_login(user.id)
    logger.info(
        "auth.2fa_verify_success",
        extra={"user_id": str(user.id)},
    )
    return AuthResponse(
        access_token=access_token,
        user=User(id=user.id, email=user.email),
    )


@auth_router.post("/logout")
async def auth_logout(
    response: Response,
    services: DepContainer,
    token: str | None = Cookie(default=None, alias="auth_token"),
    token_from_header: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> MessageResponse:
    effective_token = token or token_from_header
    if effective_token:
        user_service = await services.aget(UserApi)
        try:
            await user_service.revoke_token(effective_token)
        except Exception:
            logger.warning("Failed to revoke token on logout", exc_info=True)

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
    result = await totp_service.activate_totp(user.id, request.code)
    logger.info(
        "auth.totp_enabled",
        extra={"user_id": str(user.id)},
    )
    return result


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
    logger.info(
        "auth.totp_disabled",
        extra={"user_id": str(user.id)},
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


@auth_router.post("/passkey/register/options")
async def auth_passkey_register_options(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> dict:
    passkey_service = await services.aget(PasskeyService)
    return await passkey_service.generate_registration_options(user.id, user.email)


@auth_router.post("/passkey/register/verify")
async def auth_passkey_register_verify(
    request: PasskeyRegisterVerifyRequest,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> PasskeyResponse:
    passkey_service = await services.aget(PasskeyService)
    result = await passkey_service.verify_registration(user.id, request)
    logger.info(
        "auth.passkey_registered",
        extra={"user_id": str(user.id), "passkey_id": str(result.id)},
    )
    return result


@auth_router.get("/passkeys")
async def auth_passkeys_list(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> list[PasskeyResponse]:
    passkey_service = await services.aget(PasskeyService)
    return await passkey_service.list_passkeys(user.id)


@auth_router.delete("/passkeys/{passkey_id}")
async def auth_passkeys_delete(
    passkey_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> MessageResponse:
    passkey_service = await services.aget(PasskeyService)
    await passkey_service.delete_passkey(passkey_id, user.id)
    logger.info(
        "auth.passkey_deleted",
        extra={"user_id": str(user.id), "passkey_id": str(passkey_id)},
    )
    return MessageResponse(message="Passkey deleted successfully")


@auth_router.patch("/passkeys/{passkey_id}")
async def auth_passkeys_patch(
    passkey_id: uuid.UUID,
    request: PasskeyUpdateRequest,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> PasskeyResponse:
    passkey_service = await services.aget(PasskeyService)
    return await passkey_service.rename_passkey(passkey_id, user.id, request.name)


@auth_router.post("/passkey/authenticate/options")
@limiter.limit("10/minute")
async def auth_passkey_authenticate_options(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    services: DepContainer,
    data: PasskeyAuthenticateOptionsRequest | None = None,
) -> dict:
    passkey_service = await services.aget(PasskeyService)
    email = data.email if data else None
    return await passkey_service.generate_authentication_options(email=email)


@auth_router.post("/passkey/authenticate/verify")
@limiter.limit("10/minute")
async def auth_passkey_authenticate_verify(
    request: Request,  # noqa: ARG001
    response: Response,
    verify_data: PasskeyAuthenticateVerifyRequest,
    services: DepContainer,
) -> AuthResponse:
    user_service = await services.aget(UserApi)
    user_repo = await services.aget(UserRepository)
    passkey_service = await services.aget(PasskeyService)

    user, _passkey = await passkey_service.verify_authentication(verify_data.credential)

    access_token = user_service.create_access_token(user.email, user.id)
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=settings.environment == "prod",
        secure=settings.environment == "prod",
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    await user_repo.update_last_login(user.id)
    logger.info(
        "auth.passkey_login_success",
        extra={"user_id": str(user.id)},
    )
    return AuthResponse(
        access_token=access_token,
        user=User(id=user.id, email=user.email),
    )
