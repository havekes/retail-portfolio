from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WatchlistItem(BaseModel):
    watchlist_id: UUID
    security_symbol: str
    added_at: datetime
