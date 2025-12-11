import uuid

import svcs
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svcs.fastapi import DepContainer

from src.database import sessionmanager
from src.external.wealthsimple import (
    WealthsimpleApiWrapper,
    wealthsimple_api_wrapper_factory,
)
from src.repositories.account import AccountRepository
from src.repositories.account_type import AccountTypeRepository
from src.repositories.external_user import ExternalUserRepository
from src.repositories.position import PositionRepository
from src.repositories.sqlalchemy.sqlalchemy_account import (
    SqlAlchemyAccountRepostory,
    sqlalchemy_account_repository_factory,
)
from src.repositories.sqlalchemy.sqlalchemy_account_type import (
    SqlAlchemyAccountTypeRepository,
    sqlalchemy_account_type_repository_factory,
)
from src.repositories.sqlalchemy.sqlalchemy_external_user import (
    SqlAlchemyExternalUserRepository,
    sqlalchemy_external_user_repository_factory,
)
from src.repositories.sqlalchemy.sqlalchemy_position import (
    SqlAlchemyPositionRepository,
    sqlalchemy_position_repository_factory,
)
from src.repositories.sqlalchemy.sqlalchemy_user import (
    SqlAlchemyUserRepository,
    sqlalchemy_user_repository_factory,
)
from src.repositories.user import UserRepository
from src.routers.external import router
from src.services.external_user import (
    ExternalUserService,
    external_user_service_factory,
)
from src.services.user import UserService, user_service_factory


@svcs.fastapi.lifespan
async def lifespan(app: FastAPI, registry: svcs.Registry):  # noqa: ARG001
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


@svcs.fastapi.lifespan
async def lifespan(app: FastAPI, registry: svcs.Registry):  # noqa: ARG001
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

    # Services
    registry.register_factory(ExternalUserService, external_user_service_factory)
    registry.register_factory(UserService, user_service_factory)

    # External API Wrapper services
    registry.register_factory(WealthsimpleApiWrapper, wealthsimple_api_wrapper_factory)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(router)


@app.get("/api/ping")
async def ping(services: DepContainer) -> dict:
    """Server healthcheck"""
    session = await services.aget(AsyncSession)

    response = {}
    if (await session.execute(select(1))).scalar() == 1:
        response["database"] = "ok"
    else:
        response["database"] = "error"

    return response
