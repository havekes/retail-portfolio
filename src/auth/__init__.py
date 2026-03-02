from svcs import Container, Registry

from src.auth.api import (
    AuthorizationApi,
    UserApi,
    authorization_api_factory,
    user_api_factory,
)
from src.auth.repository import UserRepository
from src.auth.repository import VerificationTokenRepository
from src.auth.repository_sqlalchemy import (
    sqlalchemy_user_repository_factory,
    sqlalchemy_verification_token_repository_factory,
)
from src.auth.service import EmailService, EmailVerificationService


async def email_verification_service_factory(container: Container) -> EmailVerificationService:
    return EmailVerificationService(
        user_repository=await container.aget(UserRepository),
        token_repository=await container.aget(VerificationTokenRepository),
        email_service=await container.aget(EmailService),
    )


def register_auth_services(registry: Registry) -> None:
    registry.register_factory(UserRepository, sqlalchemy_user_repository_factory)
    registry.register_factory(
        VerificationTokenRepository, sqlalchemy_verification_token_repository_factory
    )
    registry.register_value(EmailService, EmailService())
    registry.register_factory(
        EmailVerificationService, email_verification_service_factory
    )
    registry.register_factory(AuthorizationApi, authorization_api_factory)
    registry.register_factory(UserApi, user_api_factory)
