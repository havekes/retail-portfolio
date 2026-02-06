from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Registry

from src.account.api import AccountApi, account_api_factory
from src.account.repository import (
    AccountRepository,
    PortfolioRepository,
    PositionRepository,
)
from src.account.repository_sqlalchemy import (
    sqlalchemy_account_repository_factory,
    sqlalchemy_portfolio_repository_factory,
    sqlalchemy_position_repository_factory,
)
from src.account.service import (
    PortfolioService,
    PositionService,
    portfolio_service_factory,
    position_service_factory,
)
from src.auth import register_auth_api
from src.config.database import sessionmanager
from src.integration import register_integration_services
from src.market import register_api_services


def register_services(registry: Registry) -> None:
    registry.register_factory(AsyncSession, sessionmanager.session)

    # Account APIs and Repositories
    registry.register_factory(AccountApi, account_api_factory)
    registry.register_factory(AccountRepository, sqlalchemy_account_repository_factory)
    registry.register_factory(
        PositionRepository, sqlalchemy_position_repository_factory
    )
    registry.register_factory(
        PortfolioRepository, sqlalchemy_portfolio_repository_factory
    )
    registry.register_factory(PositionService, position_service_factory)
    registry.register_factory(PortfolioService, portfolio_service_factory)

    register_auth_api(registry)
    register_api_services(registry)
    register_integration_services(registry)
