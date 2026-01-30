from svcs import Registry

from src.auth.api import (
    AuthorizationApi,
    UserApi,
    authorization_api_factory,
    user_api_factory,
)


def register_auth_api(registry: Registry) -> None:
    registry.register_factory(UserApi, user_api_factory)
    registry.register_factory(AuthorizationApi, authorization_api_factory)
