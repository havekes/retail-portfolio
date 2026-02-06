from abc import ABC, abstractmethod
from typing import override


class EntityNotFoundError(Exception, ABC):
    entity_id: str
    entity_name: str

    @override
    def __str__(self) -> str:
        return f"Entity {self.entity_name} with ID {self.entity_id} not found."


class AuthorizationError(Exception, ABC):
    @abstractmethod
    def log_message(self) -> str:
        """Return a log message describing the error."""

    @override
    def __str__(self) -> str:
        return "User is not authorized to perform this action."
