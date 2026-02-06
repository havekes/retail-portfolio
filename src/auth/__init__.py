from svcs import Registry

from src.auth.api import (
    AuthorizationApi,
    UserApi,
    authorization_api_factory,
    user_api_factory,
)
from src.auth.repository import UserRepository
from src.auth.repository_sqlalchemy import (
    sqlalchemy_user_repository_factory,
)


def register_auth_api(registry: Registry) -> None:
    registry.register_factory(UserRepository, sqlalchemy_user_repository_factory)
    registry.register_factory(UserApi, user_api_factory)
    registry.register_factory(AuthorizationApi, authorization_api_factory)
