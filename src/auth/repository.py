from abc import ABC, abstractmethod

from src.auth.schema import UserSchema


class UserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> UserSchema | None:
        pass

    @abstractmethod
    async def create_user(self, email: str, plain_text_password: str) -> UserSchema:
        pass
