from uuid import UUID

from fastapi import APIRouter, HTTPException
from svcs.fastapi import DepContainer

from src.enums import InstitutionEnum
from src.external import get_external_api_wrapper_class
from src.external.schemas.accounts import ExternalAccount
from src.repositories.account import AccountRepository
from src.repositories.external_user import ExternalUserRepository
from src.schemas.external import (
    ExternalImportAccountsRequest,
    ExternalImportPositionsRequest,
    ExternalImportResponse,
    ExternalLoginRequest,
    ExternalLoginResponse,
)
from src.schemas.external_user import PublicExternalUserRead
from src.services.external_user import ExternalUserService
from src.services.user import UserService

router = APIRouter(prefix="/api/external")


@router.get("/{institution}/users")
async def external_users(
    institution: InstitutionEnum, services: DepContainer
) -> list[PublicExternalUserRead]:
    """
    Get all saved external users for the given institution.
    """
    user_service = await services.aget(UserService)
    external_user_repository = await services.aget(ExternalUserRepository)

    external_users = await external_user_repository.get_by_user_and_institution(
        user_id=(await user_service.get_current_user()).id,
        institution_id=institution.value,
    )

    return [
        PublicExternalUserRead.model_validate(external_user)
        for external_user in external_users
    ]


@router.post("/{institution}/login")
async def external_login(
    institution: InstitutionEnum,
    login_request: ExternalLoginRequest,
    services: DepContainer,
) -> ExternalLoginResponse:
    """
    Login to an external institution with external username and password.
    Will create or reuse an ExternalAccount record.
    External password is never saved and external username will stay on the backend
    """
    external_user_service = await services.aget(ExternalUserService)
    external_api_wrapper = await services.aget(
        get_external_api_wrapper_class(institution)
    )
    user_service = await services.aget(UserService)

    _ = await external_user_service.get_or_create(
        user=await user_service.get_current_user(),
        institution=institution,
        username=login_request.username,
    )

    success = external_api_wrapper.login(
        username=login_request.username,
        password=login_request.password,
        otp=login_request.otp,
    )

    return ExternalLoginResponse(login_succes=success)


@router.get("/{institution}/{external_user_id}/accounts")
async def external_accounts(
    institution: InstitutionEnum,
    external_user_id: UUID,
    services: DepContainer,
) -> list[ExternalAccount]:
    """List"""
    external_user_repository = await services.aget(ExternalUserRepository)
    external_api_wrapper = await services.aget(
        get_external_api_wrapper_class(institution)
    )

    external_user = await external_user_repository.get(external_user_id)

    if not external_user:
        raise HTTPException(status_code=404, detail="External user not found")

    return await external_api_wrapper.list_accounts(external_user)


@router.post("/{institution}/accounts/import")
async def external_import_accounts(
    institution: InstitutionEnum,
    import_request: ExternalImportAccountsRequest,
    services: DepContainer,
) -> ExternalImportResponse:
    """
    Import accounts from an external institution.
    You can pass a
    """
    external_user_repository = await services.aget(ExternalUserRepository)
    external_api_wrapper = await services.aget(
        get_external_api_wrapper_class(institution)
    )

    external_user = await external_user_repository.get(
        external_user_id=import_request.external_user_id,
    )

    if not external_user:
        raise HTTPException(status_code=404, detail="External user not found")

    imported_accounts = await external_api_wrapper.import_accounts(
        external_user=external_user,
        account_ids=import_request.external_account_ids
        if len(import_request.external_account_ids or []) > 0
        else None,
    )

    return ExternalImportResponse(imported_count=len(imported_accounts))


@router.post("/{institution}/positions/import")
async def external_import_positions(
    institution: InstitutionEnum,
    import_request: ExternalImportPositionsRequest,
    services: DepContainer,
) -> ExternalImportResponse:
    """
    Import positions from an external institution.
    """
    account_repository = await services.aget(AccountRepository)
    external_user_repository = await services.aget(ExternalUserRepository)
    external_api_wrapper = await services.aget(
        get_external_api_wrapper_class(institution)
    )

    external_user = await external_user_repository.get(
        external_user_id=import_request.external_user_id
    )

    if not external_user:
        raise HTTPException(status_code=404, detail="External user not found")

    account = await account_repository.get(import_request.account_id)

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    imported_positions = await external_api_wrapper.import_positions(
        external_user=external_user,
        account=account,
    )

    return ExternalImportResponse(imported_count=len(imported_positions))
