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


class WatchlistOrderIdentityError(Exception):
    """Raised when an order payload is not a permutation of the membership.

    Deliberately not an ``EntityNotFoundError`` so it is not translated to a
    404 by the global handler; routers translate it to HTTP 422.
    """

    def __init__(self) -> None:
        super().__init__(
            "Order payload must be an exact permutation of the watchlist's "
            "current securities."
        )


class WatchlistDuplicateNameError(Exception):
    """Raised when a user already owns a watchlist with the given name.

    Deliberately not an ``EntityNotFoundError`` so it is not translated to a
    404 by the global handler; routers translate it to HTTP 409.
    """

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"A watchlist named '{name}' already exists.")


class MarketDataNotFoundError(Exception):
    """Raised when market data for a symbol is not available.

    Provider-agnostic: neither the type nor the message names the upstream
    data source. Deliberately not an ``EntityNotFoundError`` so the global
    handler does not translate it to a 404; callers decide the mapping.
    """

    def __init__(self, symbol: str, detail: str | None = None) -> None:
        self.symbol = symbol
        message = f"No market data found for symbol '{symbol}'."
        if detail:
            message = f"{message} {detail}"
        super().__init__(message)


class MarketDataProviderError(Exception):
    """Raised when the upstream market data source fails or is unavailable.

    Provider-agnostic: neither the type nor the default message names the
    upstream data source.
    """

    def __init__(self, message: str = "The market data provider is unavailable."):
        super().__init__(message)


class MarketDataConfigurationError(Exception):
    """Raised when market data provider configuration is missing or invalid.

    Provider-agnostic: neither the type nor the default message names the
    upstream data source.
    """

    def __init__(
        self,
        message: str = "Market data provider configuration is invalid.",
    ):
        super().__init__(message)
