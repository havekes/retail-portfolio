from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Reminder(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str | None = None
    trigger_date: datetime
    is_recurring: bool = False
    recurring_type: str | None = None
    is_active: bool = True

