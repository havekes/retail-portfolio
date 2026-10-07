from abc import ABC, abstractmethod
from decimal import Decimal

import keyring
from keyrings.alt.file import PlaintextKeyring

from src.core.enum import InstitutionEnum
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

    async def get_cash_balances(
        self,
        integration_user: IntegrationUserSchema,  # noqa: ARG002
        broker_account_id: BrokerAccountId,  # noqa: ARG002
    ) -> dict[str, Decimal]:
        """Return cash balances by currency code (currency -> amount).

        Non-abstract: gateways that cannot report cash inherit this no-op and
        return ``{}``. Callers must treat that as "cash not reported" rather
        than a zero balance, so they never clear a ``free_cash`` that came from
        another source (e.g. CSV import).
        """
        return {}
