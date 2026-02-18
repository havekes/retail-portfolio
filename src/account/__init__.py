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
    AccountService,
    PortfolioService,
    PositionService,
    account_service_factory,
    portfolio_service_factory,
    position_service_factory,
)


def register_account_services(registry: Registry):
    registry.register_factory(AccountRepository, sqlalchemy_account_repository_factory)
    registry.register_factory(
        PortfolioRepository, sqlalchemy_portfolio_repository_factory
    )
    registry.register_factory(
        PositionRepository, sqlalchemy_position_repository_factory
    )
    registry.register_factory(AccountApi, account_api_factory)
    registry.register_factory(AccountService, account_service_factory)
    registry.register_factory(PortfolioService, portfolio_service_factory)
    registry.register_factory(PositionService, position_service_factory)
