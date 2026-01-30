import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, cast, override
from uuid import UUID

import keyring
from svcs import Container
from ws_api import WealthsimpleAPI
from ws_api.exceptions import (
    LoginFailedException,
    ManualLoginRequired,
    OTPRequiredException,
)
from ws_api.session import WSAPISession

from src.enums import AccountTypeEnum, InstitutionEnum
from src.external.api_wrapper import ExternalAPIWrapper
from src.external.eodhd import EodhdApiWrapper
from src.external.exceptions import (
    AccountTypeUnkownError,
    LoginFailedError,
    OTPRequiredError,
    SessionDoesNotExistError,
    SessionExpiredError,
    UnsupportedSecurityError,
)
from src.external.schemas.accounts import ExternalAccount
from src.integration.brokers import BrokerApiGateway
from src.repositories.account import AccountRepository
from src.repositories.account_type import AccountTypeRepository
from src.repositories.position import PositionRepository
from src.repositories.security import SecurityRepository
from src.schemas import Account, FullExternalUser, Position, Security
from src.schemas.security import SecurityWrite

logger = logging.getLogger(__name__)


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

    async def _account_exists(self, user_id: UUID, ws_account_id: str) -> bool:
        return await self._account_repository.exists_by_user_and_external_id(
            user_id, ws_account_id
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
    async def list_accounts(
        self,
        external_user: FullExternalUser,
    ) -> list[ExternalAccount]:
        ws_client = self._get_client(external_user.external_user_id)
        ws_accounts = cast("list[dict[str, Any]]", ws_client.get_accounts())  # pyright: ignore[reportExplicitAny]
        accounts: list[ExternalAccount] = []

        for ws_account in ws_accounts:
            if ws_account["status"] != "open":
                continue

            account_type = self._get_from_unified_account_type(
                ws_account["unifiedAccountType"]
            )
            custodian_account = ws_account["custodianAccounts"][0]
            current_amount = float(
                custodian_account["financials"]["current"]["netLiquidationValue"][
                    "amount"
                ]
            )

            if account_type is None:
                continue  # Unsupported account

            accounts.append(
                ExternalAccount(
                    id=ws_account["id"],
                    type=account_type,
                    currency=ws_account["currency"],
                    display_name=custodian_account["id"],
                    value=f"{current_amount:.2f}",
                    created_at=datetime.strptime(
                        ws_account["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ"
                    ).astimezone(UTC),
                )
            )

        return accounts

    @override
    async def import_accounts(
        self,
        external_user: FullExternalUser,
        account_ids: list[str] | None = None,
    ) -> list[Account]:
        ws_client = self._get_client(external_user.external_user_id)
        ws_accounts = cast("list[dict[str, Any]]", ws_client.get_accounts())  # pyright: ignore[reportExplicitAny]
        created_accounts: list[Account] = []

        for ws_account in ws_accounts:
            ws_account_id = ws_account["id"]

            if account_ids is not None and ws_account_id not in account_ids:
                logger.info(
                    "Skipped importing account %s: not in list %s",
                    ws_account_id,
                    account_ids,
                )
                continue

            if ws_account["status"] != "open":
                logger.info(
                    "Skipped importing account %s: status not open",
                    ws_account_id,
                )
                continue

            account_exists = await self._account_exists(
                external_user.user_id,
                ws_account["id"],
            )
            if account_exists is True:
                logger.info(
                    "Skipped importing account %s: already imported",
                    ws_account_id,
                )
                continue

            account_type = self._get_from_unified_account_type(
                ws_account["unifiedAccountType"]
            )
            # Should not happen if account was returned by list method
            if account_type is None:
                raise AccountTypeUnkownError(ws_account["unifiedAccountType"])

            account = await self._account_repository.create_account(
                Account(
                    external_id=ws_account["id"],
                    name=ws_account["description"],
                    user_id=external_user.user_id,
                    account_type_id=account_type.value,
                    institution_id=self._institution.value,
                    currency=ws_account["currency"],
                )
            )
            logger.info(
                "Imported account %s for user %s",
                account.external_id,
                external_user.user_id,
            )

        return created_accounts

    @override
    async def import_positions(
        self,
        external_user: FullExternalUser,
        account: Account,
    ) -> list[Position]:
        ws_client = self._get_client(external_user.external_user_id)
        ws_balances = cast(
            "dict[str, float]", ws_client.get_account_balances(account.external_id)
        )
        positions: list[Position] = []
        _ = await self._position_repository.delete_by_account(account.id)

        for security_id, ws_balance in ws_balances.items():
            if security_id == "sec-c-cad":
                logger.info("Skipping cash position: not yet supported")
                continue

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

            try:
                average_cost = self._get_average_cost(account, ws_positions)
                security = await self._import_security(ws_security_market_data)
                position = await self._import_position(
                    account, security, ws_balance, average_cost
                )

                logger.info(
                    "Imported position %s for account %s",
                    trimmed_security_id,
                    account.id,
                )

                positions.append(position)
            except UnsupportedSecurityError:
                logger.warning("Skipped security %s: unsupported security")
                continue

        return positions

    async def _import_security(self, ws_security_market_data: dict) -> Security:  # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
        stock_info = cast("dict[str, Any]", ws_security_market_data["stock"])  # pyright: ignore[reportExplicitAny]

        if stock_info["primaryExchange"] is None:
            raise UnsupportedSecurityError

        market_cap = float(ws_security_market_data["fundamentals"]["marketCap"])  # pyright: ignore[reportUnknownArgumentType]

        eodhd_symbol = self._map_eodhd_symbol(stock_info["symbol"])
        eodhd_exchange = self._map_eodhd_exchange(stock_info["primaryExchange"])
        eodhd_result = self._eodhd.search(f"{eodhd_symbol}.{eodhd_exchange}")[0]

        return await self._security_repository.get_or_create(
            SecurityWrite(
                symbol=eodhd_result["Code"],
                name=eodhd_result["Name"],
                market_cap=market_cap,
                isin=eodhd_result["ISIN"] or "",
                currency=eodhd_result["Currency"],
                exchange=eodhd_result["Exchange"],
            )
        )

    async def _import_position(
        self,
        account: Account,
        security: Security,
        balance: float,
        average_cost: float | None,
    ) -> Position:
        return await self._position_repository.create_or_update(
            Position(
                id=uuid.uuid4(),
                account_id=account.id,
                security_id=security.id,
                quantity=balance,
                average_cost=average_cost,
            )
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
        account: Account,
        ws_positions: list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
    ) -> float | None:
        average_cost = None
        for ws_position in ws_positions:
            if ws_position["accounts"][0]["id"] == account.external_id:
                average_cost = ws_position["averagePrice"]["amount"]

        return average_cost

    def _get_from_unified_account_type(
        self, ws_unified_account_type: str
    ) -> AccountTypeEnum | None:
        if ws_unified_account_type == "SELF_DIRECTED_TFSA":
            return AccountTypeEnum.TFSA
        if ws_unified_account_type == "SELF_DIRECTED_RRSP":
            return AccountTypeEnum.RRSP
        if ws_unified_account_type == "SELF_DIRECTED_FHSA":
            return AccountTypeEnum.FHSA
        if ws_unified_account_type == "SELF_DIRECTED_NON_REGISTERED":
            return AccountTypeEnum.NON_REGISTERED
        return None

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
    container: Container,
) -> AsyncGenerator[WealthsimpleApiWrapper]:
    yield WealthsimpleApiWrapper(
        account_repository=await container.aget(AccountRepository),
        account_type_repository=await container.aget(AccountTypeRepository),
        position_repository=await container.aget(PositionRepository),
        security_repository=await container.aget(SecurityRepository),
        eodhd=container.get(EodhdApiWrapper),
    )
