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
    def __init__(self, account_type: str) -> None:
        self.account_type = account_type

    def __repr__(self) -> str:
        return f'Account type "{self.account_type}" unkown'


class IncorrectAccountError(Exception):
    pass
