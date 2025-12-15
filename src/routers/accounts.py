from fastapi import APIRouter
from svcs.fastapi import DepContainer

from src.repositories.account import AccountRepository
from src.schemas.account import Account
from src.services.user import UserService

router = APIRouter(prefix="/api/accounts")


@router.get("/")
async def accounts_list(services: DepContainer) -> list[Account]:
    """
    Get all accounts for the current user.
    """
    user_service = await services.aget(UserService)
    account_repository = await services.aget(AccountRepository)

    current_user = await user_service.get_current_user()
    return await account_repository.get_by_user(current_user.id)
