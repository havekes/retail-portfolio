import logging

import svcs
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svcs.fastapi import DepContainer

from src.config.settings import settings
from src.database import sessionmanager
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
from src.routers.accounts import router as account_router
from src.routers.auth import router as auth_router
from src.routers.external import router as external_router
from src.routers.positions import router as positions_router
from src.services.auth import AuthService, auth_service_factory
from src.services.external_user import (
    ExternalUserService,
    external_user_service_factory,
)
from src.services.position import PositionService, position_service_factory
from src.services.user import UserService, user_service_factory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)

requests_logger = logging.getLogger("urllib3")
requests_logger.setLevel(logging.DEBUG)
requests_logger.propagate = True


@svcs.fastapi.lifespan
async def lifespan(_: FastAPI, registry: svcs.Registry):
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
    registry.register_factory(ExternalUserService, external_user_service_factory)
    registry.register_factory(PositionService, position_service_factory)
    registry.register_factory(UserService, user_service_factory)
    # External API Wrapper services
    registry.register_factory(WealthsimpleApiWrapper, wealthsimple_api_wrapper_factory)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="retail-portfolio",
    version="0.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allow_origins.split(",")],
    allow_credentials=True,
    allow_methods=[origin.strip() for origin in settings.cors_allow_methods.split(",")],
    allow_headers=[origin.strip() for origin in settings.cors_allow_headers.split(",")],
)

app.include_router(external_router)
app.include_router(account_router)
app.include_router(positions_router)
app.include_router(auth_router)


@app.get("/api/ping")
async def ping(services: DepContainer) -> dict[str, str]:
    """Server healthcheck"""
    session = await services.aget(AsyncSession)

    response: dict[str, str] = {}
    response["ping"] = "pong"
    try:
        if (await session.execute(select(1))).scalar() == 1:
            response["database"] = "ok"
        else:
            response["database"] = "error"
    except Exception:
        logger.exception("Ping DB check failed")
        response["database"] = "error"

    return response
