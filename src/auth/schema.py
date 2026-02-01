from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.auth.api_types import UserId
from src.auth.model import _password_hasher


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UserId
    email: str
    password: str  # hashed
    is_active: bool = True
    last_login_at: datetime | None = None
    created_at: datetime

    def verify_password(self, plain_text_password: str) -> bool:
        """Verifies the password against the stored hash."""
        try:
            return _password_hasher.verify(self.password, plain_text_password)
        except Exception:  # noqa: BLE001
            return False
