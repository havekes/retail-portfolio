from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.auth.api_types import UserId


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UserId
    email: str
    password: str
    is_active: bool = True
    last_login_at: datetime | None = None
    created_at: datetime
