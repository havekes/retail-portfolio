from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    password: str
    is_active: bool = True
    last_login_at: Optional[datetime] = None
    created_at: datetime
