import sys
from unittest.mock import MagicMock, patch

from src.market.commands.get_search import main


def test_get_search():
    mock_gateway = MagicMock()
    mock_results = [{"Code": "AAPL", "Name": "Apple Inc"}]
    mock_gateway.search.return_value = mock_results

    test_args = ["get_search.py", "Apple"]
    with (
        patch.object(sys, "argv", test_args),
        patch("src.market.commands.get_search.eodhd_gateway_factory", return_value=mock_gateway),
        patch("src.market.commands.get_search.rprint") as mock_rprint,
    ):
        main()

    mock_gateway.search.assert_called_once_with("Apple")
    mock_rprint.assert_called_once_with(mock_results)
