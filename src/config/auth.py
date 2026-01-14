from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from svcs.fastapi import DepContainer

from src.services.user import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def current_user(
    token: Annotated[str, Depends(oauth2_scheme)], services: DepContainer
):
    user_service = await services.aget(UserService)
    yield await user_service.get_current_user_from_token(token)
