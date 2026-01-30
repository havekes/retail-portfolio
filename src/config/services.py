from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Registry

from src.account import register_account_apis
from src.auth import register_auth_api
from src.database import sessionmanager
from src.market import register_api_services


def register_services(registry: Registry) -> None:
    registry.register_factory(AsyncSession, sessionmanager.session)

    register_account_apis(registry)
    register_auth_api(registry)
    register_api_services(registry)
