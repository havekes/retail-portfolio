from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class Note(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    content: str
    account_id: UUID | None = None
    security_symbol: str | None = None
    created_at: datetime
    updated_at: datetime

