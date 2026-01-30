from uuid import UUID

from pydantic import BaseModel

from src.auth.api_types import UserId

type IntegrationUserId = UUID


class IntegrationUser(BaseModel):
    id: IntegrationUserId
    user_id: UserId
    institution_id: int
    display_name: str | None = None


class IntegrationLoginRequest(BaseModel):
    username: str
    password: str
    otp: str | None = None


class IntegrationLoginResponse(BaseModel):
    login_succes: bool


class IntegrationImportAccountsRequest(BaseModel):
    external_user_id: UUID
    external_account_ids: list[str]


class IntegrationImportPositionsRequest(BaseModel):
    external_user_id: UUID
    account_id: UUID


class IntegrationImportResponse(BaseModel):
    imported_count: int
