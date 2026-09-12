from decimal import Decimal

import pytest

from src.account.csv.exceptions import (
    CsvEmptyError,
    CsvHeaderValidationError,
    CsvRowValidationError,
)
from src.account.csv.parser import (
    GenericCsvParser,
    calculate_average_cost,
    map_account_type,
)
from src.commands.seed import WEALTHSIMPLE_CSV_FORMAT
from src.core.enum import AccountTypeEnum

WS_HEADER = (
    "Account Name,Account Type,Account Classification,Account Number,"
    "Symbol,Exchange,MIC,Name,Security Type,Quantity,Position Direction,"
    "Market Price,Market Price Currency,Book Value (CAD),Book Value Currency (CAD),"
    "Book Value,Currency,Market Value,Market Value Currency,"
    "Market Unrealized Returns,Market Unrealized Returns Currency"
)


def test_parser_valid_single_account():
    """Verify single account parsing with equity positions and cash row filtering."""
    csv_content = (
        f"{WS_HEADER}\n"
        "My TFSA,Tax-Free Savings Account,Personal,W123456789,"
        "VGRO,TSX,XTSE,Vanguard Growth ETF Portfolio,Equity,100,LONG,"
        "32.50,CAD,3000.00,CAD,3000.00,CAD,3250.00,CAD,250.00,CAD\n"
        "My TFSA,Tax-Free Savings Account,Personal,W123456789,"
        "sec-c-cad,TSX,,Canadian Dollar,Cash,500.00,LONG,"
        "1.00,CAD,500.00,CAD,500.00,CAD,500.00,CAD,0.00,CAD\n"
    )

    accounts = GenericCsvParser.parse(csv_content, WEALTHSIMPLE_CSV_FORMAT)

    assert len(accounts) == 1
    acc = accounts[0]
    assert acc.account_number == "W123456789"
    assert acc.account_name == "My TFSA"
    assert acc.account_type_id == AccountTypeEnum.TFSA
    assert acc.account_type_name == "TFSA"
    assert acc.currency == "CAD"
    assert acc.positions_count == 1
    assert len(acc.positions) == 1

    pos = acc.positions[0]
    assert pos.symbol == "VGRO"
    assert pos.exchange == "TSX"
    assert pos.name == "Vanguard Growth ETF Portfolio"
    assert pos.quantity == Decimal("100")
    assert pos.average_cost == Decimal("30.0000")
    assert pos.currency == "CAD"


def test_parser_valid_multiple_accounts():
    """Verify multiple accounts parsing grouped by account_number."""
    csv_content = (
        f"{WS_HEADER}\n"
        "My TFSA,Tax-Free Savings Account,Personal,W111111111,"
        "VGRO,TSX,XTSE,Vanguard Growth ETF Portfolio,Equity,100,LONG,"
        "30.00,CAD,3000.00,CAD,3000.00,CAD,3000.00,CAD,0.00,CAD\n"
        "My RRSP,Registered Retirement Savings Plan,Personal,W222222222,"
        "AAPL,NASDAQ,XNAS,Apple Inc.,Equity,50,LONG,"
        "150.00,USD,7500.00,USD,7500.00,USD,7500.00,USD,0.00,USD\n"
        "My RRSP,Registered Retirement Savings Plan,Personal,W222222222,"
        "MSFT,NASDAQ,XNAS,Microsoft Corporation,Equity,25,LONG,"
        "300.00,USD,7000.00,USD,7000.00,USD,7500.00,USD,500.00,USD\n"
    )

    accounts = GenericCsvParser.parse(csv_content, WEALTHSIMPLE_CSV_FORMAT)

    assert len(accounts) == 2

    tfsa = accounts[0]
    assert tfsa.account_number == "W111111111"
    assert tfsa.account_name == "My TFSA"
    assert tfsa.account_type_id == AccountTypeEnum.TFSA
    assert tfsa.currency == "CAD"
    assert tfsa.positions_count == 1
    assert len(tfsa.positions) == 1
    assert tfsa.positions[0].symbol == "VGRO"

    rrsp = accounts[1]
    assert rrsp.account_number == "W222222222"
    assert rrsp.account_name == "My RRSP"
    assert rrsp.account_type_id == AccountTypeEnum.RRSP
    assert rrsp.currency == "USD"
    assert rrsp.positions_count == 2
    assert len(rrsp.positions) == 2
    assert rrsp.positions[0].symbol == "AAPL"
    assert rrsp.positions[0].average_cost == Decimal("150.0000")
    assert rrsp.positions[1].symbol == "MSFT"
    assert rrsp.positions[1].average_cost == Decimal("280.0000")


def test_parser_missing_headers():
    """Verify fewer columns in CSV header raises CsvHeaderValidationError."""
    short_header = "Account Name,Account Type,Account Number,Symbol,Quantity"
    csv_content = f"{short_header}\nTFSA,Tax-Free Savings Account,W123,VGRO,10"

    with pytest.raises(CsvHeaderValidationError) as exc_info:
        GenericCsvParser.parse(csv_content, WEALTHSIMPLE_CSV_FORMAT)

    assert "Header column count mismatch" in str(exc_info.value)


def test_parser_invalid_headers():
    """Verify mismatched column name in CSV header raises CsvHeaderValidationError."""
    wrong_header = WS_HEADER.replace("Account Name", "Unknown Column")
    csv_content = f"{wrong_header}\nTFSA,Tax-Free Savings Account,..."

    with pytest.raises(CsvHeaderValidationError) as exc_info:
        GenericCsvParser.parse(csv_content, WEALTHSIMPLE_CSV_FORMAT)

    assert "Header mismatch at column 1" in str(exc_info.value)


def test_parser_empty_file():
    """Verify empty string or whitespace-only content raises CsvEmptyError."""
    with pytest.raises(CsvEmptyError) as exc_info:
        GenericCsvParser.parse("", WEALTHSIMPLE_CSV_FORMAT)
    assert "CSV content is empty" in str(exc_info.value)

    with pytest.raises(CsvEmptyError) as exc_info:
        GenericCsvParser.parse("   \n\n  \t  ", WEALTHSIMPLE_CSV_FORMAT)
    assert "CSV content is empty" in str(exc_info.value)


def test_account_type_mapping():
    """Verify supported variations map to AccountTypeEnum and unsupported values raise error."""
    # TFSA variations
    assert map_account_type("TFSA") == AccountTypeEnum.TFSA
    assert map_account_type("Tax-Free Savings Account") == AccountTypeEnum.TFSA
    assert map_account_type("SELF_DIRECTED_TFSA") == AccountTypeEnum.TFSA
    assert map_account_type("tax free savings account") == AccountTypeEnum.TFSA

    # RRSP variations
    assert map_account_type("RRSP") == AccountTypeEnum.RRSP
    assert map_account_type("Registered Retirement Savings Plan") == AccountTypeEnum.RRSP
    assert map_account_type("SELF_DIRECTED_RRSP") == AccountTypeEnum.RRSP

    # FHSA variations
    assert map_account_type("FHSA") == AccountTypeEnum.FHSA
    assert map_account_type("First Home Savings Account") == AccountTypeEnum.FHSA
    assert map_account_type("SELF_DIRECTED_FHSA") == AccountTypeEnum.FHSA

    # Non-Registered variations
    assert map_account_type("Non-Registered") == AccountTypeEnum.NON_REGISTERED
    assert map_account_type("Personal") == AccountTypeEnum.NON_REGISTERED
    assert map_account_type("Non-registered") == AccountTypeEnum.NON_REGISTERED
    assert map_account_type("NON_REGISTERED") == AccountTypeEnum.NON_REGISTERED
    assert (
        map_account_type("SELF_DIRECTED_NON_REGISTERED")
        == AccountTypeEnum.NON_REGISTERED
    )
    assert map_account_type("Margin") == AccountTypeEnum.NON_REGISTERED

    # Unsupported account type
    with pytest.raises(CsvRowValidationError) as exc_info:
        map_account_type("Crypto Account")
    assert "Unsupported account type: 'Crypto Account'" in str(exc_info.value)


def test_average_cost_calculation():
    """Verify average cost calculation and edge cases."""
    # Standard: 1500 / 100 = 15.0000
    avg = calculate_average_cost(Decimal("100"), Decimal("1500"))
    assert avg == Decimal("15.0000")

    # Rounding: 100 / 3 = 33.333333... -> 33.3333
    avg_rounded = calculate_average_cost(Decimal("3"), Decimal("100"))
    assert avg_rounded == Decimal("33.3333")

    # Zero quantity -> None (no ZeroDivisionError)
    assert calculate_average_cost(Decimal("0"), Decimal("100")) is None

    # Negative quantity -> None
    assert calculate_average_cost(Decimal("-5"), Decimal("100")) is None

    # None book value -> None
    assert calculate_average_cost(Decimal("10"), None) is None

    # Zero book value -> Decimal("0.0000")
    assert calculate_average_cost(Decimal("10"), Decimal("0")) == Decimal("0.0000")


def test_parser_utf8_bom():
    """Verify CSV with UTF-8 BOM is parsed without errors."""
    csv_content = (
        f"\ufeff{WS_HEADER}\n"
        "My TFSA,Tax-Free Savings Account,Personal,W123456789,"
        "XIU,TSX,XTSE,iShares S&P/TSX 60 Index ETF,Equity,200,LONG,"
        "30.00,CAD,6000.00,CAD,6000.00,CAD,6000.00,CAD,0.00,CAD\n"
    )

    accounts = GenericCsvParser.parse(csv_content, WEALTHSIMPLE_CSV_FORMAT)
    assert len(accounts) == 1
    assert accounts[0].positions[0].symbol == "XIU"
    assert accounts[0].positions[0].average_cost == Decimal("30.0000")
