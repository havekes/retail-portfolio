from uuid import UUID

from pydantic import BaseModel, ConfigDict
from ws_api.wealthsimple_api import uuid


class FullExternalUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    user_id: UUID
    institution_id: int
    external_user_id: str


class PublicExternalUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    user_id: UUID
    institution_id: int
