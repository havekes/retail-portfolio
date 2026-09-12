class CsvParserError(Exception):
    """Base exception for all CSV parser errors."""


class CsvHeaderValidationError(CsvParserError):
    """Raised when CSV headers are invalid or do not match template columns."""


class CsvHeaderCountMismatchError(CsvHeaderValidationError):
    """Raised when the CSV header column count differs from expected."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(
            f"Header column count mismatch: expected {expected}, got {actual}"
        )


class CsvHeaderColumnMismatchError(CsvHeaderValidationError):
    """Raised when a CSV header column name does not match expected."""

    def __init__(self, column: int, expected: str, actual: str) -> None:
        super().__init__(
            f"Header mismatch at column {column}: expected '{expected}', got '{actual}'"
        )


class CsvEmptyError(CsvParserError):
    """Raised when the CSV file or content is empty."""

    def __init__(self, message: str = "CSV content is empty") -> None:
        super().__init__(message)


class CsvTemplateEmptyError(CsvEmptyError):
    """Raised when the institution template string is empty."""

    def __init__(self) -> None:
        super().__init__("CSV template is empty")


class CsvNoColumnsDefinedError(CsvEmptyError):
    """Raised when no columns are parsed from the template."""

    def __init__(self) -> None:
        super().__init__("No columns defined in template")


class CsvRowValidationError(CsvParserError):
    """Raised when a CSV row cannot be parsed or contains invalid values."""


class CsvUnsupportedAccountTypeError(CsvRowValidationError):
    """Raised when an account type is not recognized."""

    def __init__(self, account_type: str) -> None:
        super().__init__(f"Unsupported account type: '{account_type}'")


class CsvMissingAccountNumberError(CsvRowValidationError):
    """Raised when a row lacks an account number."""

    def __init__(self, row_idx: int) -> None:
        super().__init__(f"Row {row_idx}: Missing account number")


class CsvMissingAccountTypeError(CsvRowValidationError):
    """Raised when a row lacks an account type."""

    def __init__(self, row_idx: int) -> None:
        super().__init__(f"Row {row_idx}: Missing account type")


class CsvInvalidQuantityError(CsvRowValidationError):
    """Raised when a position row has an invalid quantity value."""

    def __init__(self, row_idx: int, qty_str: str, symbol: str) -> None:
        super().__init__(
            f"Row {row_idx}: Invalid quantity '{qty_str}' for symbol '{symbol}'"
        )
