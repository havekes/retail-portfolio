from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Registry

from src.database import sessionmanager
from src.external.api_ninjas import ApiNinjas, api_ninjas_factory
from src.external.wealthsimple import (
    WealthsimpleApiWrapper,
    wealthsimple_api_wrapper_factory,
)
from src.repositories.account import AccountRepository
from src.repositories.account_type import AccountTypeRepository
from src.repositories.external_user import ExternalUserRepository
from src.repositories.position import PositionRepository
from src.repositories.security import SecurityRepository
from src.repositories.sqlalchemy.sqlalchemy_account import (
    sqlalchemy_account_repository_factory,
)
from src.repositories.sqlalchemy.sqlalchemy_account_type import (
    sqlalchemy_account_type_repository_factory,
)
from src.repositories.sqlalchemy.sqlalchemy_external_user import (
    sqlalchemy_external_user_repository_factory,
)
from src.repositories.sqlalchemy.sqlalchemy_position import (
    sqlalchemy_position_repository_factory,
)
from src.repositories.sqlalchemy.sqlalchemy_security import (
    sqlaclhemy_security_repository_factory,
)
from src.repositories.sqlalchemy.sqlalchemy_user import (
    sqlalchemy_user_repository_factory,
)
from src.repositories.user import UserRepository
from src.services.auth import AuthService, auth_service_factory
from src.services.authorization import (
    AuthorizationService,
    authorization_service_factory,
)
from src.services.external_user import (
    ExternalUserService,
    external_user_service_factory,
)
from src.services.position import PositionService, position_service_factory
from src.services.user import UserService, user_service_factory


def register_services(registry: Registry) -> None:
    registry.register_factory(AsyncSession, sessionmanager.session)
    # Repositories
    registry.register_factory(AccountRepository, sqlalchemy_account_repository_factory)
    registry.register_factory(
        AccountTypeRepository, sqlalchemy_account_type_repository_factory
    )
    registry.register_factory(
        ExternalUserRepository, sqlalchemy_external_user_repository_factory
    )
    registry.register_factory(
        PositionRepository, sqlalchemy_position_repository_factory
    )
    registry.register_factory(UserRepository, sqlalchemy_user_repository_factory)
    registry.register_factory(
        SecurityRepository, sqlaclhemy_security_repository_factory
    )
    # Services
    registry.register_factory(AuthService, auth_service_factory)
    registry.register_factory(AuthorizationService, authorization_service_factory)
    registry.register_factory(ExternalUserService, external_user_service_factory)
    registry.register_factory(PositionService, position_service_factory)
    registry.register_factory(UserService, user_service_factory)
    # External API Wrapper services
    registry.register_factory(ApiNinjas, api_ninjas_factory)
    registry.register_factory(WealthsimpleApiWrapper, wealthsimple_api_wrapper_factory)
