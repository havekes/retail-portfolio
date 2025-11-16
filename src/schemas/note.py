from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class Note(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    content: str
    account_id: Optional[UUID] = None
    security_symbol: Optional[str] = None
    created_at: datetime
    updated_at: datetime

