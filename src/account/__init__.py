from svcs import Registry

from src.account.api import AccountApi, account_api_factory
from src.account.service import (
    AccountService,
    PortfolioService,
    account_service_factory,
    portfolio_service_factory,
)


def register_account_apis(registry: Registry):
    registry.register_factory(AccountApi, account_api_factory)
    registry.register_factory(AccountService, account_service_factory)
    registry.register_factory(PortfolioService, portfolio_service_factory)
