from svcs import Registry

from src.account.api import AccountApi, account_api_factory


def register_account_apis(registry: Registry):
    registry.register_factory(AccountApi, account_api_factory)
