from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class Reminder(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str] = None
    trigger_date: datetime
    is_recurring: bool = False
    recurring_type: Optional[str] = None
    is_active: bool = True

