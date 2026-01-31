import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast, override

import keyring
from ws_api import WealthsimpleAPI
from ws_api.exceptions import (
    LoginFailedException,
    ManualLoginRequired,
    OTPRequiredException,
)
from ws_api.session import WSAPISession

from src.account.enum import AccountTypeEnum, InstitutionEnum
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.api_types import (
    BrokerAccount,
    BrokerAccountId,
    BrokerPosition,
)
from src.integration.brokers.exceptions import (
    AccountTypeUnkownError,
    LoginFailedError,
    OTPRequiredError,
    SessionDoesNotExistError,
    SessionExpiredError,
)
from src.integration.schema import IntegrationUserSchema

logger = logging.getLogger(__name__)


_wealthsimple_account_type_map = {
    "SELF_DIRECTED_TFSA": AccountTypeEnum.TFSA,
    "SELF_DIRECTED_RRSP": AccountTypeEnum.RRSP,
    "SELF_DIRECTED_FHSA": AccountTypeEnum.FHSA,
    "SELF_DIRECTED_NON_REGISTERED": AccountTypeEnum.NON_REGISTERED,
}


class WealthsimpleApiGateway(BrokerApiGateway):
    _username: str
    _keyring_prefix: str = "retail_prtofolio_wealthsimple"
    _institution: InstitutionEnum = InstitutionEnum.WEALTHSIMPLE

    def _get_client(self, username: str) -> WealthsimpleAPI:
        return WealthsimpleAPI.from_token(
            self._get_session(username),
            username=username,
            persist_session_fct=self._save_session,
        )

    def _get_session(self, username: str) -> WSAPISession:
        session_str = keyring.get_password(
            f"{self._keyring_prefix}.{username}", "session"
        )

        if session_str is None:
            raise SessionDoesNotExistError

        return WSAPISession.from_json(session_str)

    def _save_session(
        self,
        session: str,
        username: str,
    ) -> None:
        keyring.set_password(f"{self._keyring_prefix}.{username}", "session", session)

    def _ws_login(self, username: str, password: str, otp: str | None) -> WSAPISession:
        return WealthsimpleAPI.login(
            username,
            password,
            otp,
            persist_session_fct=self._save_session,
        )

    @override
    def login(
        self,
        username: str,
        password: str | None = None,
        otp: str | None = None,
    ) -> bool:
        """Login into Wealthsimple account using user's credentials

        First will check if session is cached.
        Will raise a SessionExpiredError if login required.
        If needed intanciate again with username and password.
        Will raise a OTPRequiredError if 2FA is active.
        If needed intanciate with username, password and OTP.
        """

        try:
            self._username = username
            # Attempt to get cached session
            _ = self._get_session(username)
            # Test if session is still valid
            self._get_client(username).get_accounts()
        except SessionDoesNotExistError:
            try:
                if password is None:
                    raise LoginFailedError
                _ = self._ws_login(username, password, otp)
            except LoginFailedException as e:
                raise LoginFailedError from e
            except OTPRequiredException as e:
                raise OTPRequiredError from e
            except ManualLoginRequired as e:
                raise SessionExpiredError from e

        logger.info("User %s logged into Wealthsimple", username)
        return True

    @override
    async def get_accounts(
        self,
        integration_user: IntegrationUserSchema,
    ) -> list[BrokerAccount]:
        ws_client = self._get_client(integration_user.external_user_id)
        ws_accounts = cast("list[dict[str, Any]]", ws_client.get_accounts())  # pyright: ignore[reportExplicitAny]
        accounts: list[BrokerAccount] = []

        for ws_account in ws_accounts:
            account = self._parse_account(ws_account)
            if account is not None:
                accounts.append(account)

        return accounts

    @override
    async def get_positions_by_account(
        self,
        integration_user: IntegrationUserSchema,
        broker_account_id: BrokerAccountId,
    ) -> list[BrokerPosition]:
        ws_client = self._get_client(integration_user.external_user_id)
        ws_balances = cast(
            "dict[str, float]", ws_client.get_account_balances(broker_account_id)
        )
        positions: list[BrokerPosition] = []

        for security_id, ws_balance in ws_balances.items():
            position = self._parse_position(
                ws_client=ws_client,
                broker_account_id=broker_account_id,
                security_id=security_id,
                ws_balance=ws_balance,
            )
            if position is not None:
                positions.append(position)

        return positions

    def _parse_account(self, ws_account: dict[str, Any]) -> BrokerAccount | None:  # pyright: ignore[reportExplicitAny]
        if ws_account["status"] != "open":
            return None

        ws_account_type = ws_account["unifiedAccountType"]
        try:
            account_type = self._get_account_type(ws_account_type)
        except AccountTypeUnkownError:
            logger.warning("Unsupported account type %s", ws_account_type)
            return None

        custodian_account = ws_account["custodianAccounts"][0]
        current_amount = Decimal(
            custodian_account["financials"]["current"]["netLiquidationValue"]["amount"]
        )

        return BrokerAccount(
            id=ws_account["id"],
            type=account_type,
            institution=InstitutionEnum.WEALTHSIMPLE,
            currency=ws_account["currency"],
            display_name=custodian_account["id"],
            value=current_amount,
            created_at=datetime.strptime(
                ws_account["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).astimezone(UTC),
        )

    def _parse_position(
        self,
        ws_client: WealthsimpleAPI,
        broker_account_id: BrokerAccountId,
        security_id: str,
        ws_balance: float,
    ) -> BrokerPosition | None:
        if security_id == "sec-c-cad":
            logger.info("Skipping cash position: not yet supported")
            return None

        # Handle API bug where security id is wrapped in []
        trimmed_security_id = security_id[1:-1]

        ws_security_market_data = ws_client.get_security_market_data(  # pyright: ignore[reportUnknownVariableType]
            trimmed_security_id
        )
        assert isinstance(ws_security_market_data, dict)

        ws_positions = self._ws_get_identity_positions(
            client=ws_client,
            security_ids=[trimmed_security_id],
        )
        assert isinstance(ws_positions, list)

        average_cost = Decimal(
            self._get_average_cost(broker_account_id, ws_positions) or 0
        )
        stock_info = cast("dict[str, Any]", ws_security_market_data["stock"])  # pyright: ignore[reportExplicitAny]

        if stock_info["primaryExchange"] is None:
            logger.warning("Skipped security %s: unsupported security")
            return None

        return BrokerPosition(
            broker_account_id=broker_account_id,
            name=stock_info["name"],
            symbol=stock_info["symbol"],
            exchange=stock_info["primaryExchange"],
            quantity=Decimal(ws_balance),
            average_cost=average_cost,
        )

    def _ws_get_identity_positions(
        self,
        client: WealthsimpleAPI,
        security_ids: list[str] | None = None,
        currency: str = "CAD",
    ):
        return client.get_identity_positions(security_ids, currency)

    def _get_average_cost(
        self,
        broker_account_id: BrokerAccountId,
        ws_positions: list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
    ) -> Decimal | None:
        for ws_position in ws_positions:
            if ws_position["accounts"][0]["id"] == broker_account_id:
                return ws_position["averagePrice"]["amount"]

        return None

    def _get_account_type(self, ws_unified_account_type: str) -> AccountTypeEnum:
        try:
            return _wealthsimple_account_type_map[ws_unified_account_type]
        except KeyError as e:
            raise AccountTypeUnkownError(ws_unified_account_type) from e

    def _map_eodhd_symbol(self, ws_symbol: str) -> str:
        return ws_symbol.replace(".", "-")

    def _map_eodhd_exchange(self, ws_primary_exchange: str) -> str:
        return {
            "CSE": "CA",
            "TSX": "TO",
            "NYSE": "US",
            "NASDAQ": "US",
        }[ws_primary_exchange]


async def wealthsimple_api_wrapper_factory() -> WealthsimpleApiGateway:
    return WealthsimpleApiGateway()
