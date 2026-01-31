from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from svcs.fastapi import DepContainer

from src.account.api import AccountApi, PositionApi
from src.account.api_types import Position
from src.account.enum import InstitutionEnum
from src.auth.api import AuthorizationApi, current_user
from src.auth.api_types import User
from src.integration.api import get_broker_gateway_class
from src.integration.api_types import (
    IntegrationImportAccountsRequest,
    IntegrationImportPositionsRequest,
    IntegrationImportResponse,
    IntegrationLoginRequest,
    IntegrationLoginResponse,
    IntegrationUser,
    IntegrationUserId,
)
from src.integration.brokers.api_types import BrokerAccount
from src.integration.repository import IntegrationUserRepository
from src.integration.repository_sqlalchemy import (
    sqlalchemy_integration_user_repository_factory,
)
from src.integration.service import (
    IntegrationUserService,
    integration_user_service_factory,
)
from src.market.api import SecurityApi

integration_router = APIRouter(prefix="/api/external")


@integration_router.get("/{institution}/users")
async def external_users(
    institution: InstitutionEnum,
    user: Annotated[User, Depends(current_user)],
    integration_user_repository: Annotated[
        IntegrationUserRepository,
        Depends(sqlalchemy_integration_user_repository_factory),
    ],
) -> list[IntegrationUser]:
    """
    Get all saved external users for the given institution.
    """
    integration_users = await integration_user_repository.get_by_user_and_institution(
        user_id=user.id,
        institution=institution,
    )

    return [
        IntegrationUser.model_validate(integration_user)
        for integration_user in integration_users
    ]


@integration_router.post("/{institution}/login")
async def external_login(
    institution: InstitutionEnum,
    login_request: IntegrationLoginRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
    integration_user_service: Annotated[
        IntegrationUserService, Depends(integration_user_service_factory)
    ],
) -> IntegrationLoginResponse:
    """
    Login to an external institution with external username and password.
    Will create or reuse an ExternalAccount record.
    External password is never saved and external username will stay on the backend
    """
    broker = await services.aget(get_broker_gateway_class(institution))

    _ = await integration_user_service.get_or_create(
        user=user,
        institution=institution,
        username=login_request.username,
    )

    success = broker.login(
        username=login_request.username,
        password=login_request.password,
        otp=login_request.otp,
    )

    return IntegrationLoginResponse(login_succes=success)


@integration_router.get("/{institution}/{external_user_id}/accounts")
async def external_accounts(
    institution: InstitutionEnum,
    external_user_id: IntegrationUserId,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
    integration_user_repository: Annotated[
        IntegrationUserRepository,
        Depends(sqlalchemy_integration_user_repository_factory),
    ],
) -> list[BrokerAccount]:
    """
    List external accounts for the current user.
    """
    authorization_service = await services.aget(AuthorizationApi)
    broker = await services.aget(get_broker_gateway_class(institution))

    integration_user = await integration_user_repository.get(external_user_id)
    authorization_service.check_entity_owned_by_user(user, integration_user)

    if not integration_user:
        raise HTTPException(status_code=404, detail="External user not found")

    return await broker.get_accounts(integration_user)


@integration_router.post("/{institution}/accounts/import")
async def external_import_accounts(
    institution: InstitutionEnum,
    import_request: IntegrationImportAccountsRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
    integration_user_repository: Annotated[
        IntegrationUserRepository,
        Depends(sqlalchemy_integration_user_repository_factory),
    ],
) -> IntegrationImportResponse:
    """
    Import accounts from an external institution.
    You can pass a list of external account ids to selectively import.
    """
    authorization_service = await services.aget(AuthorizationApi)
    broker = await services.aget(get_broker_gateway_class(institution))
    account_api = await services.aget(AccountApi)

    integration_user = await integration_user_repository.get(
        import_request.external_user_id
    )
    authorization_service.check_entity_owned_by_user(user, integration_user)

    if not integration_user:
        raise HTTPException(status_code=404, detail="External user not found")

    broker_accounts = await broker.get_accounts(
        integration_user=integration_user,
    )

    imported_accounts = await account_api.import_from_broker(broker_accounts, user.id)

    return IntegrationImportResponse(imported_count=len(imported_accounts))


@integration_router.post("/{institution}/positions/import")
async def external_import_positions(
    institution_id: InstitutionEnum,
    import_request: IntegrationImportPositionsRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
    integration_user_repository: Annotated[
        IntegrationUserRepository,
        Depends(sqlalchemy_integration_user_repository_factory),
    ],
) -> IntegrationImportResponse:
    """
    Import positions from an external institution for a given account.
    """
    authorization_service = await services.aget(AuthorizationApi)
    account_api = await services.aget(AccountApi)
    security_api = await services.aget(SecurityApi)
    position_api = await services.aget(PositionApi)
    broker = await services.aget(get_broker_gateway_class(institution_id))

    integration_user = await integration_user_repository.get(
        integration_user_id=import_request.external_user_id
    )
    authorization_service.check_entity_owned_by_user(user, integration_user)

    if not integration_user:
        raise HTTPException(status_code=404, detail="External user not found")

    account = await account_api.get_by_id(import_request.account_id)
    broker_account_id = await account_api.get_broker_id_by_id(import_request.account_id)

    if account is None or broker_account_id is None:
        raise HTTPException(status_code=404, detail="Account not found")

    broker_positions = await broker.get_positions_by_account(
        integration_user=integration_user,
        broker_account_id=broker_account_id,
    )

    positions: list[Position] = []
    for broker_position in broker_positions:
        security = await security_api.get_or_create_from_broker(
            institution_id=institution_id,
            broker_symbol=broker_position.symbol,
            broker_exchange=broker_position.exchange,
            broker_name=broker_position.name,
        )

        positions.append(
            broker_position.to_position(account_id=account.id, security_id=security.id)
        )

    imported_positions = position_api.create(positions)

    return IntegrationImportResponse(imported_count=len(imported_positions))
