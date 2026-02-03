from svcs import Registry
from svcs.fastapi import DepContainer

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
    # Create wrappers that svcs will properly detect as taking a container
    async def user_repository_factory(svcs_container: DepContainer):
        return await sqlalchemy_user_repository_factory(svcs_container)

    async def authorization_api_wrapper(svcs_container: DepContainer):
        return await authorization_api_factory(svcs_container)

    registry.register_factory(UserRepository, user_repository_factory)
    registry.register_factory(UserApi, user_api_factory)
    registry.register_factory(AuthorizationApi, authorization_api_wrapper)
