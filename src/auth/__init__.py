from svcs import Container, Registry

from src.auth.api import (
    AuthorizationApi,
    UserApi,
    authorization_api_factory,
    user_api_factory,
)
from src.auth.repository import (
    RecoveryCodeRepository,
    TotpRepository,
    UserRepository,
    VerificationTokenRepository,
)
from src.auth.repository_sqlalchemy import (
    sqlalchemy_recovery_code_repository_factory,
    sqlalchemy_totp_repository_factory,
    sqlalchemy_user_repository_factory,
    sqlalchemy_verification_token_repository_factory,
)
from src.auth.service import EmailVerificationService, TotpService
from src.core.email import EmailService


async def email_verification_service_factory(
    container: Container,
) -> EmailVerificationService:
    return EmailVerificationService(
        user_repository=await container.aget(UserRepository),
        token_repository=await container.aget(VerificationTokenRepository),
        email_service=await container.aget(EmailService),
    )


async def totp_service_factory(
    container: Container,
) -> TotpService:
    return TotpService(
        totp_repository=await container.aget(TotpRepository),
        recovery_code_repository=await container.aget(RecoveryCodeRepository),
        user_repository=await container.aget(UserRepository),
    )


def register_auth_services(registry: Registry) -> None:
    registry.register_factory(UserRepository, sqlalchemy_user_repository_factory)
    registry.register_factory(
        VerificationTokenRepository, sqlalchemy_verification_token_repository_factory
    )
    registry.register_factory(TotpRepository, sqlalchemy_totp_repository_factory)
    registry.register_factory(
        RecoveryCodeRepository, sqlalchemy_recovery_code_repository_factory
    )
    registry.register_factory(
        EmailVerificationService, email_verification_service_factory
    )
    registry.register_factory(TotpService, totp_service_factory)
    registry.register_factory(AuthorizationApi, authorization_api_factory)
    registry.register_factory(UserApi, user_api_factory)
