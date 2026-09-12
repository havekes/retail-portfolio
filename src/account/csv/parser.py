import csv
import io
import re
from collections.abc import Iterator
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from src.account.csv.exceptions import (
    CsvEmptyError,
    CsvHeaderColumnMismatchError,
    CsvHeaderCountMismatchError,
    CsvInvalidQuantityError,
    CsvMissingAccountNumberError,
    CsvMissingAccountTypeError,
    CsvNoColumnsDefinedError,
    CsvTemplateEmptyError,
    CsvUnsupportedAccountTypeError,
)
from src.account.csv.schema import CsvDiscoveredAccount, CsvPositionRecord
from src.core.enum import AccountTypeEnum


def normalize_token(token: str) -> str:
    """Normalize a header or template token to lowercase snake_case."""
    cleaned = token.lstrip("\ufeff").strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        cleaned = cleaned[1:-1]
    return re.sub(r"[^a-z0-9]+", "_", cleaned.lower()).strip("_")


ACCOUNT_TYPE_MAP: dict[str, AccountTypeEnum] = {
    # TFSA
    "tfsa": AccountTypeEnum.TFSA,
    "tax-free savings account": AccountTypeEnum.TFSA,
    "tax free savings account": AccountTypeEnum.TFSA,
    "self_directed_tfsa": AccountTypeEnum.TFSA,
    # RRSP
    "rrsp": AccountTypeEnum.RRSP,
    "registered retirement savings plan": AccountTypeEnum.RRSP,
    "self_directed_rrsp": AccountTypeEnum.RRSP,
    # FHSA
    "fhsa": AccountTypeEnum.FHSA,
    "first home savings account": AccountTypeEnum.FHSA,
    "self_directed_fhsa": AccountTypeEnum.FHSA,
    # Non-Registered / Personal
    "non-registered": AccountTypeEnum.NON_REGISTERED,
    "non_registered": AccountTypeEnum.NON_REGISTERED,
    "non registered": AccountTypeEnum.NON_REGISTERED,
    "personal": AccountTypeEnum.NON_REGISTERED,
    "self_directed_non_registered": AccountTypeEnum.NON_REGISTERED,
    "margin": AccountTypeEnum.NON_REGISTERED,
}

ACCOUNT_TYPE_DISPLAY_NAMES: dict[AccountTypeEnum, str] = {
    AccountTypeEnum.TFSA: "TFSA",
    AccountTypeEnum.RRSP: "RRSP",
    AccountTypeEnum.FHSA: "FHSA",
    AccountTypeEnum.NON_REGISTERED: "Non-Registered",
}


def map_account_type(val: str) -> AccountTypeEnum:
    """Map raw account type string to AccountTypeEnum."""
    cleaned = val.strip().lower()
    if cleaned in ACCOUNT_TYPE_MAP:
        return ACCOUNT_TYPE_MAP[cleaned]
    raise CsvUnsupportedAccountTypeError(val)


def is_cash_row(symbol: str | None, security_type: str | None) -> bool:
    """Detect cash or non-equity holding rows."""
    sec_clean = (security_type or "").strip().lower()
    sym_clean = (symbol or "").strip().lower()
    return (
        not sym_clean
        or sec_clean == "cash"
        or sym_clean == "cash"
        or sym_clean.startswith("sec-c-")
    )


def calculate_average_cost(
    quantity: Decimal, book_value: Decimal | None
) -> Decimal | None:
    """Safely compute average cost as book_value / quantity."""
    if quantity <= Decimal(0) or book_value is None:
        return None
    return (book_value / quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _parse_template(template: str) -> list[str]:
    template_reader = csv.reader(io.StringIO(template.strip()))
    template_rows = [r for r in template_reader if r]
    if not template_rows or not template_rows[0]:
        raise CsvTemplateEmptyError

    expected_tokens = [normalize_token(col) for col in template_rows[0] if col.strip()]
    if not expected_tokens:
        raise CsvNoColumnsDefinedError
    return expected_tokens


def _validate_headers(
    csv_reader: Iterator[list[str]], expected_tokens: list[str]
) -> None:
    header_row: list[str] | None = None
    for row in csv_reader:
        if any(cell.strip() for cell in row):
            header_row = row
            break

    if header_row is None:
        raise CsvEmptyError

    raw_headers = [cell.strip() for cell in header_row]
    if len(raw_headers) != len(expected_tokens):
        raise CsvHeaderCountMismatchError(len(expected_tokens), len(raw_headers))

    actual_headers = [normalize_token(col) for col in raw_headers]
    for idx, (expected, actual) in enumerate(
        zip(expected_tokens, actual_headers, strict=False)
    ):
        if expected != actual:
            raise CsvHeaderColumnMismatchError(idx + 1, expected, actual)


def _parse_position(
    row_dict: dict[str, str], row_idx: int, account_currency: str
) -> CsvPositionRecord | None:
    symbol = row_dict.get("symbol", "").strip()
    security_type = row_dict.get("security_type", "").strip()
    if is_cash_row(symbol, security_type):
        return None

    qty_str = row_dict.get("quantity", "").strip()
    try:
        qty_clean = qty_str.replace(",", "")
        quantity = Decimal(qty_clean)
    except (InvalidOperation, ValueError) as e:
        raise CsvInvalidQuantityError(row_idx, qty_str, symbol) from e

    book_val_str = row_dict.get("book_value", "").strip()
    book_value: Decimal | None = None
    if book_val_str:
        try:
            bv_clean = book_val_str.replace(",", "").replace("$", "")
            book_value = Decimal(bv_clean)
        except (InvalidOperation, ValueError):  # fmt: skip
            book_value = None

    avg_cost = calculate_average_cost(quantity, book_value)
    exchange = row_dict.get("exchange", "").strip() or None
    pos_name = row_dict.get("name", "").strip() or None
    pos_currency = row_dict.get("currency", "").strip() or account_currency

    return CsvPositionRecord(
        symbol=symbol,
        exchange=exchange,
        name=pos_name,
        quantity=quantity,
        average_cost=avg_cost,
        currency=pos_currency,
    )


class GenericCsvParser:
    """Template-driven CSV parser service for broker account imports."""

    map_account_type = staticmethod(map_account_type)

    @classmethod
    def parse(cls, content_str: str, template: str) -> list[CsvDiscoveredAccount]:
        if not content_str or not content_str.strip():
            raise CsvEmptyError

        clean_content = content_str.lstrip("\ufeff")
        expected_tokens = _parse_template(template)

        csv_reader = iter(csv.reader(io.StringIO(clean_content)))
        _validate_headers(csv_reader, expected_tokens)

        accounts_order: list[str] = []
        accounts_data: dict[str, dict] = {}

        for row_idx, row in enumerate(csv_reader, start=2):
            if not any(cell.strip() for cell in row):
                continue

            row_dict = {
                expected_tokens[i]: row[i].strip() if i < len(row) else ""
                for i in range(len(expected_tokens))
            }

            account_num = row_dict.get("account_number", "").strip()
            if not account_num:
                raise CsvMissingAccountNumberError(row_idx)

            if account_num not in accounts_data:
                raw_acc_type = row_dict.get("account_type", "").strip()
                if not raw_acc_type:
                    raise CsvMissingAccountTypeError(row_idx)
                acc_type_id = map_account_type(raw_acc_type)
                acc_type_name = ACCOUNT_TYPE_DISPLAY_NAMES.get(
                    acc_type_id, acc_type_id.name
                )
                account_name = row_dict.get("account_name", "").strip()
                currency = row_dict.get("currency", "").strip() or "CAD"

                accounts_order.append(account_num)
                accounts_data[account_num] = {
                    "account_number": account_num,
                    "account_name": account_name,
                    "account_type_id": acc_type_id,
                    "account_type_name": acc_type_name,
                    "currency": currency,
                    "positions": [],
                }

            position = _parse_position(
                row_dict, row_idx, accounts_data[account_num]["currency"]
            )
            if position is not None:
                accounts_data[account_num]["positions"].append(position)

        return [
            CsvDiscoveredAccount(
                account_number=accounts_data[acc_num]["account_number"],
                account_name=accounts_data[acc_num]["account_name"],
                account_type_id=accounts_data[acc_num]["account_type_id"],
                account_type_name=accounts_data[acc_num]["account_type_name"],
                currency=accounts_data[acc_num]["currency"],
                positions_count=len(accounts_data[acc_num]["positions"]),
                positions=accounts_data[acc_num]["positions"],
            )
            for acc_num in accounts_order
        ]
