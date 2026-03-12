from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from svcs.fastapi import DepContainer

from src.account.api.account import AccountApi
from src.account.api.institution import InstitutionApi
from src.account.api.position import PositionApi
from src.account.api_types import Institution, Position
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
    IntegrationUserUpdateDisplayNameRequest,
)
from src.integration.brokers.api_types import BrokerAccount
from src.integration.brokers.exceptions import LoginFailedError, OTPRequiredError
from src.integration.repository import IntegrationUserRepository
from src.integration.service import (
    IntegrationUserService,
)
from src.integration.task import sync_account_positions_task
from src.market.api import SecurityApi

integration_router = APIRouter(prefix="/api/external")
institutions_router = APIRouter(prefix="/api/integration")


@institutions_router.get("/institutions")
async def integration_institutions(
    services: DepContainer,
    _user: Annotated[User, Depends(current_user)],
) -> list[Institution]:
    """
    Get all institutions with enabled integrations.
    """
    institution_api = await services.aget(InstitutionApi)
    return await institution_api.get_all_enabled_integrations()


@integration_router.get("/users")
async def integration_users(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> list[IntegrationUser]:
    """
    Get all saved external users for all supported institutions.
    """
    integration_user_repository = await services.aget(IntegrationUserRepository)
    integration_users = await integration_user_repository.get_by_user(
        user_id=user.id,
    )

    return [
        IntegrationUser.model_validate(integration_user)
        for integration_user in integration_users
    ]


@integration_router.patch("/users/{external_user_id}/display_name")
async def integration_update_user_display_name(
    external_user_id: IntegrationUserId,
    update_request: IntegrationUserUpdateDisplayNameRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
) -> IntegrationUser:
    """
    Update the display name of an external user.
    """
    authorization_service = await services.aget(AuthorizationApi)
    integration_user_repository = await services.aget(IntegrationUserRepository)

    integration_user = await integration_user_repository.get(external_user_id)
    if not integration_user:
        raise HTTPException(status_code=404, detail="External user not found")

    authorization_service.check_entity_owned_by_user(user, integration_user)

    await integration_user_repository.update_display_name(
        integration_user_id=external_user_id,
        display_name=update_request.display_name,
    )

    integration_user.display_name = update_request.display_name
    return IntegrationUser.model_validate(integration_user)


@integration_router.post("/{institution}/login")
async def integration_login(
    institution: InstitutionEnum,
    login_request: IntegrationLoginRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
) -> IntegrationLoginResponse:
    """
    Login to an external institution with external username and password.
    Will create or reuse an ExternalAccount record.
    External password is never saved and external username will stay on the backend
    """
    broker = await services.aget(get_broker_gateway_class(institution))
    integration_user_service = await services.aget(IntegrationUserService)

    _ = await integration_user_service.get_or_create(
        user=user,
        institution=institution,
        username=login_request.username,
    )

    try:
        success = broker.login(
            username=login_request.username,
            password=login_request.password,
            otp=login_request.otp,
        )
    except OTPRequiredError as e:
        raise HTTPException(status_code=400, detail="OTP_REQUIRED") from e
    except LoginFailedError as e:
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS") from e

    return IntegrationLoginResponse(login_succes=success)


@integration_router.get("/users/{external_user_id}/accounts")
async def integration_accounts(
    external_user_id: IntegrationUserId,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
) -> list[BrokerAccount]:
    """
    List external accounts for the current user.
    """
    authorization_service = await services.aget(AuthorizationApi)
    integration_user_repository = await services.aget(IntegrationUserRepository)

    integration_user = await integration_user_repository.get(external_user_id)
    if not integration_user:
        raise HTTPException(status_code=404, detail="External user not found")

    authorization_service.check_entity_owned_by_user(user, integration_user)

    broker = await services.aget(
        get_broker_gateway_class(integration_user.institution_id)
    )

    return await broker.get_accounts(integration_user)


@integration_router.post("/accounts/import")
async def integration_import_accounts(
    import_request: IntegrationImportAccountsRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
) -> IntegrationImportResponse:
    """
    Import accounts from an external institution.
    You can pass a list of external account ids to selectively import.
    Position syncing is delegated to the Huey task queue (huey-worker).
    """
    integration_user_repository = await services.aget(IntegrationUserRepository)
    authorization_service = await services.aget(AuthorizationApi)
    account_api = await services.aget(AccountApi)

    integration_user = await integration_user_repository.get(
        import_request.external_user_id
    )
    if not integration_user:
        raise HTTPException(status_code=404, detail="External user not found")

    authorization_service.check_entity_owned_by_user(user, integration_user)

    broker = await services.aget(
        get_broker_gateway_class(integration_user.institution_id)
    )

    broker_accounts = await broker.get_accounts(
        integration_user=integration_user,
    )

    broker_accounts = [
        acc for acc in broker_accounts if acc.id in import_request.external_account_ids
    ]

    imported_accounts = await account_api.import_from_broker(
        broker_accounts, user.id, integration_user.id
    )

    for account in imported_accounts:
        sync_account_positions_task.delay(
            user.id,
            account,
            account.external_id,
            get_broker_gateway_class(integration_user.institution_id),
        )

    return IntegrationImportResponse(imported_count=len(imported_accounts))


@integration_router.post("/positions/import")
async def integration_import_positions(
    import_request: IntegrationImportPositionsRequest,
    services: DepContainer,
    user: Annotated[User, Depends(current_user)],
) -> IntegrationImportResponse:
    """
    Import positions from an external institution for a given account.
    """
    integration_user_repository = await services.aget(IntegrationUserRepository)
    authorization_service = await services.aget(AuthorizationApi)
    account_api = await services.aget(AccountApi)
    security_api = await services.aget(SecurityApi)
    position_api = await services.aget(PositionApi)

    integration_user = await integration_user_repository.get(
        integration_user_id=import_request.external_user_id
    )
    if not integration_user:
        raise HTTPException(status_code=404, detail="External user not found")

    authorization_service.check_entity_owned_by_user(user, integration_user)

    broker = await services.aget(
        get_broker_gateway_class(integration_user.institution_id)
    )

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
            institution_id=integration_user.institution_id,
            broker_symbol=broker_position.symbol,
            broker_exchange=broker_position.exchange,
            broker_name=broker_position.name,
        )

        positions.append(
            broker_position.to_position(account_id=account.id, security_id=security.id)
        )

    imported_positions = position_api.create(positions)

    return IntegrationImportResponse(imported_count=len(imported_positions))
