from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from ws_api.wealthsimple_api import uuid


class Account(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = uuid.uuid4()
    external_id: str
    name: str
    user_id: UUID
    account_type_id: int
    institution_id: int
    is_active: bool = True
    created_at: datetime | None = None
    currency: str
    deleted_at: datetime | None = None
