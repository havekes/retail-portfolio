import keyring
from ws_api import WealthsimpleAPI
from ws_api.exceptions import (
    LoginFailedException,
    ManualLoginRequired,
    OTPRequiredException,
)
from ws_api.session import WSAPISession

from src.enums import AccountTypeEnum, InstitutionEnum
from src.external.exceptions import (
    AccountTypeUnkownError,
    IncorrectAccountError,
    LoginFailedError,
    OTPRequiredError,
    SessionDoesNotExistError,
    SessionExpiredError,
    UnknownError,
)
from src.external.wrapper import ExternalAPIWrapper
from src.schemas import Account, AccountType


class Wealthsimple(ExternalAPIWrapper):
    _keyring_prefix: str = "retail_prtofolio_wealthsimple"
    _institution: InstitutionEnum = InstitutionEnum.WEALTHSIMPLE

    _username: str
    _ws_session: WSAPISession

    @property
    def _client(self) -> WealthsimpleAPI:
        return WealthsimpleAPI.from_token(
            self._get_session(self._username),
            username=self._username,
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

    async def _account_exists(self, ws_account_id: str) -> bool:
        return await self._account_repository.exists_account_by_user_and_external_id(
            self._user.id, ws_account_id
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
            self._client.get_accounts()
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

    async def import_accounts(self) -> list[Account]:
        ws_accounts = self._client.get_accounts()
        created_accounts = []

        for ws_account in ws_accounts:
            account_archived = ws_account["archivedAt"] is not None
            if account_archived is True:
                continue

            account_exists = await self._account_exists(ws_account["id"])
            if account_exists is True:
                continue

            try:
                account_type = await self._get_account_type(ws_account["type"])
            except AccountTypeUnkownError:
                continue

            await self._account_repository.create_account(
                Account(
                    external_id=ws_account["id"],
                    name=ws_account["description"],
                    user_id=self._user.id,
                    account_type_id=account_type.id,
                    institution_id=self._institution.value,
                )
            )

        return created_accounts

    async def import_positions(self, account: Account):
        if account.user_id != self._user.id:
            raise IncorrectAccountError

        if account.institution_id != self._institution.value:
            raise IncorrectAccountError
