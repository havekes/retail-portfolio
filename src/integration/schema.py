from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.account.api_types import InstitutionEnum
from src.auth.api_types import UserId
from src.integration.api_types import IntegrationUserId
from src.integration.brokers.api_types import BrokerUserId


class IntegrationUserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: IntegrationUserId
    user_id: UserId
    institution_id: InstitutionEnum
    external_user_id: BrokerUserId
    last_used_at: datetime | None = None
    display_name: str | None = None
