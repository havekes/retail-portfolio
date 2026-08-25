from svcs import Registry

from src.auth.api import (
    AuthorizationApi,
    UserApi,
    authorization_api_factory,
    user_api_factory,
)
from src.auth.repository import (
    PasskeyRepository,
    RecoveryCodeRepository,
    TotpRepository,
    UserRepository,
    VerificationTokenRepository,
)
from src.auth.repository_sqlalchemy import (
    sqlalchemy_passkey_repository_factory,
    sqlalchemy_recovery_code_repository_factory,
    sqlalchemy_totp_repository_factory,
    sqlalchemy_user_repository_factory,
    sqlalchemy_verification_token_repository_factory,
)
from src.auth.service import (
    EmailVerificationService,
    PasskeyService,
    TotpService,
    email_verification_service_factory,
    passkey_service_factory,
    totp_service_factory,
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
    registry.register_factory(PasskeyRepository, sqlalchemy_passkey_repository_factory)
    registry.register_factory(
        EmailVerificationService, email_verification_service_factory
    )
    registry.register_factory(TotpService, totp_service_factory)
    registry.register_factory(PasskeyService, passkey_service_factory)
    registry.register_factory(AuthorizationApi, authorization_api_factory)
    registry.register_factory(UserApi, user_api_factory)
