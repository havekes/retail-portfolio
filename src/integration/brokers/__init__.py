from abc import ABC, abstractmethod

import keyring
from keyrings.alt.file import PlaintextKeyring

from src.account.api_types import InstitutionEnum
from src.integration.brokers.api_types import (
    BrokerAccount,
    BrokerAccountId,
    BrokerPosition,
)
from src.integration.schema import IntegrationUserSchema


class BrokerApiGateway(ABC):
    _keyring_prefix: str
    _institution: InstitutionEnum

    def __init__(self):
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
    async def get_accounts(
        self, integration_user: IntegrationUserSchema
    ) -> list[BrokerAccount]:
        pass

    @abstractmethod
    async def get_positions_by_account(
        self,
        integration_user: IntegrationUserSchema,
        broker_account_id: BrokerAccountId,
    ) -> list[BrokerPosition]:
        pass
