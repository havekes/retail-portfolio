from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from ws_api.wealthsimple_api import uuid


class FullExternalUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    institution_id: int
    external_user_id: str
    last_used_at: datetime | None
    display_name: str | None


class PublicExternalUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    institution_id: int
    display_name: str | None
