from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.dependencies.core import DBSessionDep
from src.enums import InstitutionEnum
from src.external import get_external_api_wrapper
from src.models.user import User as UserModel
from src.schemas import User
from src.schemas.external import ExternalLoginRequest

router = APIRouter(prefix="/api/external")


async def get_user(session: AsyncSession) -> User:
    q = (
        select(UserModel)
        .filter(UserModel.email == "greg@havek.es")
        .options(joinedload(UserModel.accounts))
    )
    user = (await session.execute(q)).scalar()
    if user is None:
        raise Exception("User not found")

    return User.model_validate(user)


@router.post("/{institution_id}/login")
async def login(
    institution_id: int,
    login_request: ExternalLoginRequest,
    session: DBSessionDep,
):
    """
    Login to an external institution.

    Note: Authentication for the user is not implemented yet.
    """
    institution = InstitutionEnum(institution_id)
    user = await get_user(session)
    wrapper = get_external_api_wrapper(institution, session, user, username=user.email)
    success = wrapper.login(
        username=login_request.username,
        password=login_request.password,
        otp=login_request.otp,
    )

    return {"login_success": success}


@router.get("/{institution_id}/import/accounts")
async def import_accounts(
    institution_id: int,
    session: DBSessionDep,
):
    """
    Login to an external institution.

    Note: Authentication for the user is not implemented yet.
    """
    institution = InstitutionEnum(institution_id)
    user = await get_user(session)
    wrapper = get_external_api_wrapper(institution, session, user, username=user.email)
    imported_accounts = await wrapper.import_accounts()

    return {"imported_accounts_count": len(imported_accounts)}
