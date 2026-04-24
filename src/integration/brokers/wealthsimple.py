import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast, override

import keyring
from ws_api import WealthsimpleAPI
from ws_api.exceptions import (
    LoginFailedException,
    ManualLoginRequired,
    OTPRequiredException,
    UnexpectedException,
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
    UnknownError,
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
    debug_api_responses: bool = False
    debug_dump_path: str | None = None

    def _get_client(self, username: str) -> WealthsimpleAPI:
        logger.debug("Getting Wealthsimple client from session for user: %s", username)

        return WealthsimpleAPI.from_token(
            self._get_session(username),
            username=username,
            persist_session_fct=self._save_session,
        )

    def _get_session(self, username: str) -> WSAPISession:
        logger.debug("Getting Wealthsimple session from keyring for user: %s", username)

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
        logger.debug("Saving Wealthsimple session tp keyring for user: %s", username)

        keyring.set_password(f"{self._keyring_prefix}.{username}", "session", session)

    def _ws_login(self, username: str, password: str, otp: str | None) -> WSAPISession:
        logger.debug("Logging in Wealthsimple for user: %s", username)

        ws = cast("Any", WealthsimpleAPI())
        original_send_get = ws.send_get

        def wrapped_send_get(url, headers=None, return_headers=False):  # noqa: FBT002
            response = original_send_get(url, headers, return_headers)
            ws._last_response = response  # noqa: SLF001
            return response

        ws.send_get = wrapped_send_get

        try:
            return ws.login_internal(
                username,
                password,
                otp,
                persist_session_fct=self._save_session,
            )
        except UnexpectedException:
            last_response = getattr(ws, "_last_response", "No response captured")
            logger.exception(
                "Wealthsimple login failed with UnexpectedException. Last Response: %s",
                last_response,
            )
            raise

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
        ws_accounts = cast("list[dict[str, Any]]", ws_client.get_accounts())

        if getattr(self, "debug_api_responses", False):
            logger.debug(
                "Raw Wealthsimple get_accounts API response:\n%s",
                json.dumps(ws_accounts, indent=2),
            )

        if self.debug_dump_path:
            with Path(self.debug_dump_path).open("w") as f:
                json.dump(ws_accounts, f, indent=2)
            logger.info("Dumped raw API response to %s", self.debug_dump_path)

        accounts: list[BrokerAccount] = []
        for ws_account in ws_accounts:
            account = self._parse_account(ws_account, integration_user.display_name)
            if account is not None:
                accounts.append(account)

        logger.info(
            "Parsed %d Wealthsimple accounts for user: %s",
            len(accounts),
            integration_user.external_user_id,
        )

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
        all_raw_ws_positions: list[list[dict[str, Any]]] = []

        for security_id, ws_balance in ws_balances.items():
            position, raw_ws_positions = self._parse_position(
                ws_client=ws_client,
                broker_account_id=broker_account_id,
                security_id=security_id,
                ws_balance=ws_balance,
            )
            if raw_ws_positions:
                all_raw_ws_positions.append(raw_ws_positions)

            if position is not None:
                logger.info(
                    "Fetched position: %s.%s",
                    position.symbol,
                    position.exchange,
                )
                positions.append(position)
            else:
                logger.warning(
                    "Could not parse position: %s",
                    security_id,
                )

        if getattr(self, "debug_api_responses", False):
            logger.debug(
                "Raw Wealthsimple get_identity_positions API responses:\n%s",
                json.dumps(all_raw_ws_positions, indent=2),
            )

        if self.debug_dump_path:
            with Path(self.debug_dump_path).open("w") as f:
                json.dump(all_raw_ws_positions, f, indent=2)
            logger.info("Dumped raw API response to %s", self.debug_dump_path)

        logger.info(
            "Parsed %d Wealthsimple positions for account: %s",
            len(positions),
            broker_account_id,
        )
        return positions

    def _parse_account(
        self,
        ws_account: dict[str, Any],
        broker_display_name: str | None = None,
    ) -> BrokerAccount | None:
        if ws_account["status"] != "open":
            logger.debug("Skipping closed Wealthsimple account: %s", ws_account["id"])
            return None

        ws_account_type = ws_account["unifiedAccountType"]
        try:
            account_type = self._get_account_type(ws_account_type)
        except AccountTypeUnkownError:
            logger.info("Unsupported account type %s", ws_account_type)
            return None

        custodian_account = ws_account["custodianAccounts"][0]
        current_amount = Decimal(
            custodian_account["financials"]["current"]["netLiquidationValue"]["amount"]
        )

        net_deposits = None
        financials = ws_account.get("financials")
        if (
            financials
            and "currentCombined" in financials
            and "netDeposits" in financials["currentCombined"]
        ):
            net_deposits = Decimal(
                financials["currentCombined"]["netDeposits"]["amount"]
            )

        logger.debug("Parsed Wealthsimple account: %s", ws_account["id"])

        return BrokerAccount(
            id=ws_account["id"],
            type=account_type,
            institution=InstitutionEnum.WEALTHSIMPLE,
            currency=ws_account["currency"],
            display_name=custodian_account["id"],
            broker_display_name=broker_display_name,
            value=current_amount,
            net_deposits=net_deposits,
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
    ) -> tuple[BrokerPosition | None, list[dict[str, Any]] | None]:
        if security_id == "sec-c-cad":
            logger.info("Skipping cash position: not yet supported")
            return None, None

        # Handle API bug where security id is wrapped in []
        trimmed_security_id = security_id[1:-1]

        ws_security_market_data = ws_client.get_security_market_data(
            trimmed_security_id
        )
        if not isinstance(ws_security_market_data, dict):
            logger.error(
                "Malformed security market data: %s",
                ws_security_market_data,
            )
            raise UnknownError

        stock_info = cast("dict[str, Any]", ws_security_market_data.get("stock", {}))

        if stock_info["primaryExchange"] is None:
            logger.info(
                "Skipped unsupported security: %s",
                trimmed_security_id,
            )
            return None, None

        # Inferred currency from exchange
        # Wealthsimple primaryExchange mapping: NYSE/NASDAQ are US, TSX/CSE are CA
        exchange = stock_info["primaryExchange"]
        currency = "USD" if exchange in ["NYSE", "NASDAQ"] else "CAD"

        ws_positions = self._ws_get_identity_positions(
            client=ws_client,
            security_ids=[trimmed_security_id],
            currency=currency,
        )
        if not isinstance(ws_positions, list):
            logger.error(
                "Malformed identity potitions: %s",
                ws_positions,
            )
            raise UnknownError

        average_cost = Decimal(
            self._get_average_cost(broker_account_id, ws_positions) or 0
        )

        return BrokerPosition(
            broker_account_id=broker_account_id,
            name=stock_info["name"],
            symbol=stock_info["symbol"],
            exchange=exchange,
            quantity=Decimal(ws_balance),
            average_cost=average_cost,
            currency=currency,
        ), ws_positions

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
        ws_positions: list[dict[str, Any]],
    ) -> Decimal | None:
        for ws_position in ws_positions:
            if ws_position["accounts"][0]["id"] == broker_account_id:
                return ws_position["averagePrice"]["amount"]

        logger.warning(
            "Could not compute average cost for account: %s",
            broker_account_id,
        )
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


async def wealthsimple_api_wrapper_factory(
    *,
    debug_api_responses: bool = False,
    debug_dump_path: str | None = None,
) -> WealthsimpleApiGateway:
    gateway = WealthsimpleApiGateway()
    gateway.debug_api_responses = debug_api_responses
    gateway.debug_dump_path = debug_dump_path
    return gateway
