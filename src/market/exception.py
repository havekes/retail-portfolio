from src.core.exception import EntityNotFoundError
from src.market.api_types import SecurityId, WatchlistId


class SecurityNotFoundError(EntityNotFoundError):
    """Raised a security does not exist within the app."""

    def __init__(self, security_id: SecurityId):
        self.entity_id = str(security_id)
        self.entity_name = "Security"

        super().__init__(str(self))


class WatchlistNotFoundError(EntityNotFoundError):
    """Raised when a watchlist does not exist within the app."""

    def __init__(self, watchlist_id: WatchlistId):
        self.entity_id = str(watchlist_id)
        self.entity_name = "Watchlist"

        super().__init__(str(self))


class WatchlistDuplicateNameError(Exception):
    """Raised when a user already owns a watchlist with the given name.

    Deliberately not an ``EntityNotFoundError`` so it is not translated to a
    404 by the global handler; routers translate it to HTTP 409.
    """

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"A watchlist named '{name}' already exists.")
