from collections.abc import AsyncGenerator

from fastapi import HTTPException
from pydantic import BaseModel
from svcs import Container

from src.schemas import User
from src.services.user import UserService


class AuthorizationService:
    _user_service: UserService

    def __init__(self, user_service: UserService) -> None:
        self._user_service = user_service

    def check_entity_owned_by_user(
        self, user: User, entity: BaseModel | None, field: str = "user_id"
    ):
        if entity is None or user.id != getattr(entity, field):
            # Hide entity existance for security reasons
            raise HTTPException(404, "Entity does not exist")

    async def check_entity_owned_by_user_from_token(
        self, token: str, entity: BaseModel | None, field: str = "user_id"
    ):
        user = await self._user_service.get_current_user_from_token(token)
        self.check_entity_owned_by_user(user, entity, field)


async def authorization_service_factory(
    container: Container,
) -> AsyncGenerator[AuthorizationService]:
    yield AuthorizationService(user_service=await container.aget(UserService))
