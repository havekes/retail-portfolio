from src.core.exception import EntityNotFoundError
from src.integration.api_types import IntegrationUserId


class IntegrationUserNotFoundError(EntityNotFoundError):
    """Raised when no broker user is found."""

    def __init__(self, integration_user_id: IntegrationUserId):
        self.entity_id = str(integration_user_id)
        self.entity_name = "IntegrationUser"

        super().__init__(str(self))


class AccountPositionsSyncError(Exception):
    pass
