import sys
from unittest.mock import MagicMock, patch

from src.market.commands.get_prices import main


def test_get_prices_default_args():
    mock_gateway = MagicMock()
    mock_gateway.get_prices.return_value = [100.0, 101.0]

    test_args = ["get_prices.py", "GOOG"]
    with (
        patch.object(sys, "argv", test_args),
        patch("src.market.commands.get_prices.eodhd_gateway_factory", return_value=mock_gateway),
        patch("src.market.commands.get_prices.rprint") as mock_rprint,
    ):
        main()

    mock_gateway.get_prices.assert_called_once()
    sec = mock_gateway.get_prices.call_args[0][0]
    assert sec.symbol == "GOOG"
    mock_rprint.assert_called_once_with([100.0, 101.0])


def test_get_prices_with_custom_dates():
    mock_gateway = MagicMock()
    mock_gateway.get_prices.return_value = [100.0]

    test_args = ["get_prices.py", "GOOG", "--from-date", "2026-01-01", "--to-date", "2026-01-10"]
    with (
        patch.object(sys, "argv", test_args),
        patch("src.market.commands.get_prices.eodhd_gateway_factory", return_value=mock_gateway),
        patch("src.market.commands.get_prices.rprint") as mock_rprint,
    ):
        main()

    mock_gateway.get_prices.assert_called_once()
    kwargs = mock_gateway.get_prices.call_args[1]
    assert kwargs["from_date"] == "2026-01-01"
    assert kwargs["to_date"] == "2026-01-10"
