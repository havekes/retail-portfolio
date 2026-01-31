from uuid import UUID

from pydantic import BaseModel

from src.account.api_types import AccountId
from src.account.enum import InstitutionEnum
from src.auth.api_types import UserId

type IntegrationUserId = UUID


class IntegrationUser(BaseModel):
    id: IntegrationUserId
    user_id: UserId
    institution_id: InstitutionEnum
    display_name: str | None = None


class IntegrationLoginRequest(BaseModel):
    username: str
    password: str
    otp: str | None = None


class IntegrationLoginResponse(BaseModel):
    login_succes: bool


class IntegrationImportAccountsRequest(BaseModel):
    external_user_id: IntegrationUserId
    external_account_ids: list[str]


class IntegrationImportPositionsRequest(BaseModel):
    external_user_id: IntegrationUserId
    account_id: AccountId


class IntegrationImportResponse(BaseModel):
    imported_count: int
