from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.enums import ActionEnum


class ActionItem(BaseModel):
    id: UUID
    security_symbol: str
    user_id: UUID
    action: ActionEnum
    reason: str | None = None
    last_updated: datetime
