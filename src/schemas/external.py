from pydantic import BaseModel


class ExternalLoginRequest(BaseModel):
    username: str
    password: str
    otp: str | None = None
