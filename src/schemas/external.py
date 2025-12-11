from uuid import UUID

from pydantic import BaseModel


class ExternalLoginRequest(BaseModel):
    username: str
    password: str
    otp: str | None = None


class ExternalLoginResponse(BaseModel):
    login_succes: bool


class ExternalImportRequest(BaseModel):
    external_user_id: str


class ExternalImportResponse(BaseModel):
    imported_count: int
