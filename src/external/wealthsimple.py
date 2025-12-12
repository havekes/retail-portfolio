import json
import logging
import uuid
from collections.abc import AsyncGenerator
from uuid import UUID

import keyring
from svcs import Container
from ws_api import WealthsimpleAPI, WSApiException
from ws_api.exceptions import (
    LoginFailedException,
    ManualLoginRequired,
    OTPRequiredException,
)
from ws_api.session import WSAPISession

from src.enums import AccountTypeEnum, InstitutionEnum
from src.external.api_wrapper import ExternalAPIWrapper
from src.external.exceptions import (
    AccountTypeUnkownError,
    LoginFailedError,
    OTPRequiredError,
    SessionDoesNotExistError,
    SessionExpiredError,
    UnknownError,
    UnsupportedSecurityError,
)
from src.repositories.account import AccountRepository
from src.repositories.account_type import AccountTypeRepository
from src.repositories.position import PositionRepository
from src.repositories.security import SecurityRepository
from src.schemas import Account, AccountType, FullExternalUser, Position, Security

logger = logging.getLogger(__name__)


class WealthsimpleApiWrapper(ExternalAPIWrapper):
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

    def _ws_login(self, username: str, password: str, otp: str | None) -> None:
        WealthsimpleAPI.login(
            username,
            password,
            otp,
            persist_session_fct=self._save_session,
        )

    async def _get_account_type(self, ws_account_type_name: str) -> AccountType:
        try:
            account_type_id = {
                "tfsa": AccountTypeEnum.TFSA,
                "rrsp": AccountTypeEnum.RRSP,
            }[ws_account_type_name].value
        except KeyError as e:
            raise AccountTypeUnkownError(ws_account_type_name) from e

        account_type = await self._account_type_repository.get_account_type(
            account_type_id
        )

        if account_type is None:
            raise UnknownError

        return account_type

    async def _account_exists(self, user_id: UUID, ws_account_id: str) -> bool:
        return await self._account_repository.exists_by_user_and_external_id(
            user_id, ws_account_id
        )

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
            self._get_session(username)
            # Test if session is still valid
            self._get_client(username).get_accounts()
        except SessionDoesNotExistError:
            try:
                if password is None:
                    raise LoginFailedError
                self._ws_login(username, password, otp)
            except LoginFailedException as e:
                raise LoginFailedError from e
            except OTPRequiredException as e:
                raise OTPRequiredError from e
            except ManualLoginRequired as e:
                raise SessionExpiredError from e

        return True

    async def import_accounts(
        self, external_user: FullExternalUser, account_ids: list[str] | None = None
    ) -> list[Account]:
        ws_client = self._get_client(external_user.external_user_id)
        ws_accounts = ws_client.get_accounts()
        created_accounts = []

        for ws_account in ws_accounts:
            # Filter by account IDs if provided
            if account_ids is not None and ws_account["id"] not in account_ids:
                continue

            # Skip archived accounts
            account_archived = ws_account["archivedAt"] is not None
            if account_archived is True:
                continue

            # Skip existing accounts
            account_exists = await self._account_exists(
                external_user.user_id, ws_account["id"]
            )
            if account_exists is True:
                continue

            # Only import known account types
            try:
                account_type = await self._get_account_type(ws_account["type"])
            except AccountTypeUnkownError:
                continue

            await self._account_repository.create_account(
                Account(
                    external_id=ws_account["id"],
                    name=ws_account["description"],
                    user_id=external_user.user_id,
                    account_type_id=account_type.id,
                    institution_id=self._institution.value,
                )
            )

        return created_accounts

    async def import_positions(
        self, external_user: FullExternalUser, account: Account
    ) -> list[Position]:
        ws_client = self._get_client(external_user.external_user_id)
        ws_balances = ws_client.get_account_balances(account.external_id)

        positions = []

        for security_id, ws_balance in ws_balances.items():
            # TODO handle cash
            if security_id == "sec-c-cad":
                logger.info("Skip importing cash amount")
                continue

            # Handle API bug
            trimmed_security_id = security_id[1:-1]

            ws_security_market_data = ws_client.get_security_market_data(
                trimmed_security_id
            )
            if not isinstance(ws_security_market_data, dict):
                logger.warning("Could not fetch security info: %s", trimmed_security_id)
                continue  # TODO handle data not found

            ws_positions = self._ws_get_identity_positions(
                client=ws_client,
                security_ids=[trimmed_security_id],
            )
            assert isinstance(ws_positions, list)
            average_cost = self._get_average_cost(account, ws_positions)

            try:
                security = await self._import_security(ws_security_market_data)
                position = await self._import_position(
                    account, security, ws_balance, average_cost
                )

                positions.append(position)
            except UnsupportedSecurityError:
                continue

        return positions

    async def _import_security(self, ws_security_market_data: dict) -> Security:
        stock_info = ws_security_market_data["stock"]

        if stock_info["primaryExchange"] is None:
            raise UnsupportedSecurityError

        symbol = f"{stock_info['primaryExchange']}:{stock_info['symbol']}"

        return await self._security_repository.get_or_create(
            Security(
                symbol=symbol,
                name=stock_info["name"],
                market_cap=ws_security_market_data["fundamentals"]["marketCap"],
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
                security_symbol=security.symbol,
                quantity=balance,
                average_cost=average_cost,
            )
        )

    def _ws_get_identity_positions(
        self,
        client: WealthsimpleAPI,
        security_ids: list | None = None,
        currency: str = "CAD",
    ):
        client.GRAPHQL_QUERIES["FetchIdentityPositions"] = (
            "query FetchIdentityPositions($identityId: ID!, $currency: Currency!, $first: Int, $cursor: String, $accountIds: [ID!], $aggregated: Boolean, $currencyOverride: CurrencyOverride, $sort: PositionSort, $sortDirection: PositionSortDirection, $filter: PositionFilter, $since: PointInTime, $includeSecurity: Boolean = false, $includeAccountData: Boolean = false, $includeOneDayReturnsBaseline: Boolean = false) {\n  identity(id: $identityId) {\n    id\n    financials(filter: {accounts: $accountIds}) {\n      current(currency: $currency) {\n        id\n        positions(\n          first: $first\n          after: $cursor\n          aggregated: $aggregated\n          filter: $filter\n          sort: $sort\n          sortDirection: $sortDirection\n        ) {\n          edges {\n            node {\n              ...PositionV2\n              __typename\n            }\n            __typename\n          }\n          pageInfo {\n            hasNextPage\n            endCursor\n            __typename\n          }\n          totalCount\n          status\n          hasOptionsPosition\n          hasCryptoPositionsOnly\n          securityTypes\n          securityCurrencies\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment SecuritySummary on Security {\n  ...SecuritySummaryDetails\n  stock {\n    ...StockSummary\n    __typename\n  }\n  quoteV2(currency: null) {\n    ...SecurityQuoteV2\n    __typename\n  }\n  optionDetails {\n    ...OptionSummary\n    __typename\n  }\n  __typename\n}\n\nfragment SecuritySummaryDetails on Security {\n  id\n  currency\n  inactiveDate\n  status\n  wsTradeEligible\n  equityTradingSessionType\n  securityType\n  active\n  securityGroups {\n    id\n    name\n    __typename\n  }\n  features\n  logoUrl\n  __typename\n}\n\nfragment StockSummary on Stock {\n  name\n  symbol\n  primaryMic\n  primaryExchange\n  __typename\n}\n\nfragment StreamedSecurityQuoteV2 on UnifiedQuote {\n  __typename\n  securityId\n  ask\n  bid\n  currency\n  price\n  sessionPrice\n  quotedAsOf\n  ... on EquityQuote {\n    marketStatus\n    askSize\n    bidSize\n    close\n    high\n    last\n    lastSize\n    low\n    open\n    mid\n    volume: vol\n    referenceClose\n    __typename\n  }\n  ... on OptionQuote {\n    marketStatus\n    askSize\n    bidSize\n    close\n    high\n    last\n    lastSize\n    low\n    open\n    mid\n    volume: vol\n    breakEven\n    inTheMoney\n    liquidityStatus\n    openInterest\n    underlyingSpot\n    __typename\n  }\n}\n\nfragment SecurityQuoteV2 on UnifiedQuote {\n  ...StreamedSecurityQuoteV2\n  previousBaseline\n  __typename\n}\n\nfragment OptionSummary on Option {\n  underlyingSecurity {\n    ...UnderlyingSecuritySummary\n    __typename\n  }\n  maturity\n  osiSymbol\n  expiryDate\n  multiplier\n  optionType\n  strikePrice\n  __typename\n}\n\nfragment UnderlyingSecuritySummary on Security {\n  id\n  stock {\n    name\n    primaryExchange\n    primaryMic\n    symbol\n    __typename\n  }\n  __typename\n}\n\nfragment PositionLeg on PositionLeg {\n  security {\n    id\n    ...SecuritySummary @include(if: $includeSecurity)\n    __typename\n  }\n  quantity\n  positionDirection\n  bookValue {\n    amount\n    currency\n    __typename\n  }\n  totalValue(currencyOverride: $currencyOverride) {\n    amount\n    currency\n    __typename\n  }\n  averagePrice {\n    amount\n    currency\n    __typename\n  }\n  percentageOfAccount\n  unrealizedReturns(since: $since) {\n    amount\n    currency\n    __typename\n  }\n  marketAveragePrice: averagePrice(currencyOverride: $currencyOverride) {\n    amount\n    currency\n    __typename\n  }\n  marketBookValue: bookValue(currencyOverride: $currencyOverride) {\n    amount\n    currency\n    __typename\n  }\n  marketUnrealizedReturns: unrealizedReturns(currencyOverride: $currencyOverride) {\n    amount\n    currency\n    __typename\n  }\n  oneDayReturnsBaselineV2(currencyOverride: $currencyOverride) @include(if: $includeOneDayReturnsBaseline) {\n    baseline {\n      currency\n      amount\n      __typename\n    }\n    useDailyPriceChange\n    __typename\n  }\n  __typename\n}\n\nfragment PositionV2 on PositionV2 {\n  id\n  quantity\n  accounts @include(if: $includeAccountData) {\n    id\n    __typename\n  }\n  percentageOfAccount\n  positionDirection\n  bookValue {\n    amount\n    currency\n    __typename\n  }\n  averagePrice {\n    amount\n    currency\n    __typename\n  }\n  marketAveragePrice: averagePrice(currencyOverride: $currencyOverride) {\n    amount\n    currency\n    __typename\n  }\n  marketBookValue: bookValue(currencyOverride: $currencyOverride) {\n    amount\n    currency\n    __typename\n  }\n  totalValue(currencyOverride: $currencyOverride) {\n    amount\n    currency\n    __typename\n  }\n  unrealizedReturns(since: $since) {\n    amount\n    currency\n    __typename\n  }\n  marketUnrealizedReturns: unrealizedReturns(currencyOverride: $currencyOverride) {\n    amount\n    currency\n    __typename\n  }\n  security {\n    id\n    ...SecuritySummary @include(if: $includeSecurity)\n    __typename\n  }\n  oneDayReturnsBaselineV2(currencyOverride: $currencyOverride) @include(if: $includeOneDayReturnsBaseline) {\n    baseline {\n      currency\n      amount\n      __typename\n    }\n    useDailyPriceChange\n    __typename\n  }\n  strategyType\n  legs {\n    ...PositionLeg\n    __typename\n  }\n  __typename\n}"
        )

        return client.do_graphql_query(
            "FetchIdentityPositions",
            {
                "identityId": client.get_token_info().get("identity_canonical_id"),
                "currency": currency,
                "filter": {"securityIds": security_ids},
                "includeAccountData": True,
            },
            "identity.financials.current.positions.edges",
            "array",
        )

    def _get_average_cost(
        self, account: Account, ws_positions: list[dict]
    ) -> float | None:
        average_cost = None
        for ws_position in ws_positions:
            if ws_position["accounts"][0]["id"] == account.external_id:
                average_cost = ws_position["averagePrice"]["amount"]

        return average_cost


async def wealthsimple_api_wrapper_factory(
    container: Container,
) -> AsyncGenerator[WealthsimpleApiWrapper]:
    yield WealthsimpleApiWrapper(
        account_repository=await container.aget(AccountRepository),
        account_type_repository=await container.aget(AccountTypeRepository),
        position_repository=await container.aget(PositionRepository),
        security_repository=await container.aget(SecurityRepository),
    )
