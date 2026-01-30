from abc import ABC, abstractmethod
from datetime import datetime

import keyring
from keyrings.alt.file import PlaintextKeyring
from pydantic import BaseModel

from src.account.api_types import Account, AccountTypeEnum, InstitutionEnum, Position
from src.integration.api_types import IntegrationUser


class BrokerAccount(BaseModel):
    id: str
    type: AccountTypeEnum
    currency: str
    display_name: str
    value: str
    created_at: datetime


class BrokerApiGateway(ABC):
    _keyring_prefix: str
    _institution: InstitutionEnum

    def __init__(
        self,
    ):
        # TODO secure this before staging deployment
        keyring.set_keyring(PlaintextKeyring())

    @abstractmethod
    def login(
        self,
        username: str,
        password: str | None = None,
        otp: str | None = None,
    ) -> bool:
        pass

    @abstractmethod
    async def list_accounts(
        self, integration_user: IntegrationUser
    ) -> list[BrokerAccount]:
        pass

    @abstractmethod
    async def import_accounts(
        self, integration_user: IntegrationUser, account_ids: list[str] | None = None
    ) -> list[Account]:
        pass

    @abstractmethod
    async def import_positions(
        self, integration_user: IntegrationUser, account: Account
    ) -> list[Position]:
        pass
