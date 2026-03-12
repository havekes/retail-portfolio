from src.exception import EntityNotFoundError
from src.market.api_types import SecurityId


class SecurityNotFoundError(EntityNotFoundError):
    """Raised a security does not exist within the app."""

    def __init__(self, security_id: SecurityId):
        self.entity_id = str(security_id)
        self.entity_name = "Security"

        super().__init__(str(self))
