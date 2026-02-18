from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Registry

from src.account import regsiter_account_services
from src.auth import register_auth_services
from src.config.database import sessionmanager
from src.integration import register_integration_services
from src.market import register_market_services


def register_services(registry: Registry) -> None:
    registry.register_factory(AsyncSession, sessionmanager.session)

    # Account APIs and Repositories
    regsiter_account_services(registry)
    register_auth_services(registry)
    register_integration_services(registry)
    register_market_services(registry)
