from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from stockholm import Money
from ws_api.wealthsimple_api import uuid


class Account(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = uuid.uuid4()
    external_id: str
    name: str
    user_id: UUID
    account_type_id: int
    institution_id: int
    currency: str
    is_active: bool = True
    created_at: datetime | None = None
    deleted_at: datetime | None = None


class AccountTotals(BaseModel):
    cost: Money


class AccountRenameRequest(BaseModel):
    name: str
