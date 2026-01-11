from typing import override


class ExternalAPIError(Exception):
    pass


class SessionDoesNotExistError(ExternalAPIError):
    pass


class SessionExpiredError(ExternalAPIError):
    pass


class LoginFailedError(ExternalAPIError):
    pass


class OTPRequiredError(ExternalAPIError):
    pass


class UnknownError(ExternalAPIError):
    pass


class AccountTypeUnkownError(ExternalAPIError):
    _account_type: str

    def __init__(self, account_type: str) -> None:
        super().__init__()
        self._account_type = account_type

    @override
    def __repr__(self) -> str:
        return f'Account type "{self._account_type}" unkown'


class IncorrectAccountError(Exception):
    pass


class UnsupportedSecurityError(Exception):
    pass
