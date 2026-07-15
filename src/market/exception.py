from src.core.exception import EntityNotFoundError
from src.market.api_types import SecurityId, WatchlistId


class SecurityNotFoundError(EntityNotFoundError):
    """Raised a security does not exist within the app."""

    def __init__(self, security_id: SecurityId):
        self.entity_id = str(security_id)
        self.entity_name = "Security"

        super().__init__(str(self))


class WatchlistNotFoundError(EntityNotFoundError):
    """Raised a watchlist does not exist within the app."""

    def __init__(self, watchlist_id: WatchlistId):
        self.entity_id = str(watchlist_id)
        self.entity_name = "Watchlist"

        super().__init__(str(self))

