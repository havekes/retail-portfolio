from datetime import date
import sys
from unittest.mock import MagicMock, patch

from src.market.commands.get_price import main


def test_get_price_default_date():
    mock_gateway = MagicMock()
    mock_gateway.get_price_on_date.return_value = 150.0

    test_args = ["get_price.py", "AAPL"]
    with (
        patch.object(sys, "argv", test_args),
        patch("src.market.commands.get_price.eodhd_gateway_factory", return_value=mock_gateway),
        patch("src.market.commands.get_price.rprint") as mock_rprint,
    ):
        main()

    mock_gateway.get_price_on_date.assert_called_once()
    sec, passed_date = mock_gateway.get_price_on_date.call_args[0]
    assert sec.symbol == "AAPL"
    assert isinstance(passed_date, date)
    mock_rprint.assert_called_once_with(150.0)


def test_get_price_with_explicit_date():
    mock_gateway = MagicMock()
    mock_gateway.get_price_on_date.return_value = 250.0

    test_args = ["get_price.py", "MSFT", "--date", "2026-01-15"]
    with (
        patch.object(sys, "argv", test_args),
        patch("src.market.commands.get_price.eodhd_gateway_factory", return_value=mock_gateway),
        patch("src.market.commands.get_price.rprint") as mock_rprint,
    ):
        main()

    mock_gateway.get_price_on_date.assert_called_once()
    sec, passed_date = mock_gateway.get_price_on_date.call_args[0]
    assert sec.symbol == "MSFT"
    assert passed_date == date(2026, 1, 15)
    mock_rprint.assert_called_once_with(250.0)
