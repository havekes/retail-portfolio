from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from svcs.fastapi import DepContainer

from src.dependencies.core import DBSessionDep
from src.enums import InstitutionEnum
from src.external import get_external_api_wrapper_class
from src.models.user import User as UserModel
from src.repositories.external_user import ExternalUserRepository
from src.schemas import User
from src.schemas.external import (
    ExternalImportRequest,
    ExternalImportResponse,
    ExternalLoginRequest,
    ExternalLoginResponse,
)
from src.schemas.external_user import FullExternalUser, PublicExternalUserRead
from src.services.external_user import ExternalUserService
from src.services.user import UserService

router = APIRouter(prefix="/api/external")


@router.get("/{institution_id}/users")
async def get_external_users(
    institution_id: int, services: DepContainer
) -> list[PublicExternalUserRead]:
    """
    Get all external users for the given institution.
    """
    institution = InstitutionEnum(institution_id)
    user_serivce = services.get(UserService)
    external_user_repository = services.get(ExternalUserRepository)

    external_users = await external_user_repository.get_by_user_and_institution(
        user_id=(await user_serivce.get_current_user()).id,
        institution_id=institution.value,
    )

    return [
        PublicExternalUserRead.model_validate(external_user)
        for external_user in external_users
    ]


@router.post("/{institution_id}/login")
async def login(
    institution_id: int, login_request: ExternalLoginRequest, services: DepContainer
) -> ExternalLoginResponse:
    """
    Login to an external institution.
    Will create or reuse an ExternalAccount record.
    """
    institution = InstitutionEnum(institution_id)
    user_serivce = services.get(UserService)
    external_user_service = services.get(ExternalUserService)
    external_api_wrapper = services.get(get_external_api_wrapper_class(institution))

    await external_user_service.get_or_create(
        user=await user_serivce.get_current_user(),
        institution=institution,
        external_user_id=login_request.username,
    )

    success = external_api_wrapper.login(
        username=login_request.username,
        password=login_request.password,
        otp=login_request.otp,
    )

    return ExternalLoginResponse(login_succes=success)


@router.get("/{institution_id}/import/accounts")
async def import_accounts(
    institution_id: int,
    import_request: ExternalImportRequest,
    services: DepContainer,
) -> ExternalImportResponse:
    """
    Import accounnts from an external institution.
    """
    institution = InstitutionEnum(institution_id)
    external_user_repository = services.get(ExternalUserRepository)
    external_api_wrapper = services.get(get_external_api_wrapper_class(institution))

    external_user = await external_user_repository.get(
        uuid=import_request.external_user_uuid
    )

    if not external_user:
        raise HTTPException(status_code=404, detail="External user not found")

    imported_accounts = await external_api_wrapper.import_accounts(
        external_user=external_user
    )

    return ExternalImportResponse(imported_count=len(imported_accounts))
