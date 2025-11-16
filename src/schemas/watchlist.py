from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Watchlist(BaseModel):
    id: UUID
    user_id: UUID
    name: str = "Main Watchlist"
    created_at: datetime
