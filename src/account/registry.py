from svcs import Registry

from src.account.api.account import (
    AccountApi,
    account_api_factory,
)
from src.account.api.institution import (
    InstitutionApi,
    institution_api_factory,
)
from src.account.api.position import (
    PositionApi,
    position_api_factory,
)
from src.account.repository import (
    AccountRepository,
    InstitutionRepository,
    PortfolioRepository,
    PositionRepository,
)
from src.account.repository_sqlalchemy import (
    sqlalchemy_account_repository_factory,
    sqlalchemy_institution_repository_factory,
    sqlalchemy_portfolio_repository_factory,
    sqlalchemy_position_repository_factory,
)
from src.account.service.account import (
    AccountService,
    account_service_factory,
)
from src.account.service.portfolio import (
    PortfolioService,
    portfolio_service_factory,
)
from src.account.service.position import (
    PositionService,
    position_service_factory,
)


def register_account_services(registry: Registry):
    registry.register_factory(AccountRepository, sqlalchemy_account_repository_factory)
    registry.register_factory(
        InstitutionRepository, sqlalchemy_institution_repository_factory
    )
    registry.register_factory(
        PortfolioRepository, sqlalchemy_portfolio_repository_factory
    )
    registry.register_factory(
        PositionRepository, sqlalchemy_position_repository_factory
    )
    registry.register_factory(AccountApi, account_api_factory)
    registry.register_factory(InstitutionApi, institution_api_factory)
    registry.register_factory(PositionApi, position_api_factory)
    registry.register_factory(AccountService, account_service_factory)
    registry.register_factory(PortfolioService, portfolio_service_factory)
    registry.register_factory(PositionService, position_service_factory)
