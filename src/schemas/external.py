from uuid import UUID

from pydantic import BaseModel


class ExternalLoginRequest(BaseModel):
    username: str
    password: str
    otp: str | None = None


class ExternalLoginResponse(BaseModel):
    login_succes: bool


class ExternalImportAccountsRequest(BaseModel):
    external_user_id: UUID


class ExternalImportPositionsRequest(BaseModel):
    external_user_id: UUID
    account_id: UUID


class ExternalImportResponse(BaseModel):
    imported_count: int
