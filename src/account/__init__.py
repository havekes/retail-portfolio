from svcs import Registry

from src.account.api import AccountApi, account_api_factory
from src.account.service import (
    AccountService,
    PortfolioService,
    PositionService,
    account_service_factory,
    portfolio_service_factory,
    position_service_factory,
)


def regsiter_account_services(registry: Registry):
    registry.register_factory(AccountApi, account_api_factory)
    registry.register_factory(AccountService, account_service_factory)
    registry.register_factory(PortfolioService, portfolio_service_factory)
    registry.register_factory(PositionService, position_service_factory)
