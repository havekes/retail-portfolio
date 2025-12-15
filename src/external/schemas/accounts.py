from datetime import datetime

from pydantic import BaseModel

from src.enums import AccountTypeEnum


class ExternalAccount(BaseModel):
    id: str
    type: AccountTypeEnum
    currency: str
    display_name: str
    value: str
    created_at: datetime
