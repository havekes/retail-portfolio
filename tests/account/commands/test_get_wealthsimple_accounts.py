import sys
from unittest.mock import AsyncMock, patch

import pytest

from src.account.commands.get_wealthsimple_accounts import main


@pytest.mark.anyio
async def test_get_wealthsimple_accounts_default():
    mock_gateway = AsyncMock()
    mock_gateway.get_accounts.return_value = ["account_1", "account_2"]

    test_args = ["get_wealthsimple_accounts.py", "user@example.com"]
    with (
        patch.object(sys, "argv", test_args),
        patch(
            "src.account.commands.get_wealthsimple_accounts.wealthsimple_api_wrapper_factory",
            new_callable=AsyncMock,
            return_value=mock_gateway,
        ) as mock_factory,
        patch("src.account.commands.get_wealthsimple_accounts.rprint") as mock_rprint,
    ):
        await main()

    mock_factory.assert_called_once_with(debug_api_responses=False, debug_dump_path=None)
    mock_gateway.get_accounts.assert_called_once()
    user_arg = mock_gateway.get_accounts.call_args[0][0]
    assert user_arg.external_user_id == "user@example.com"
    mock_rprint.assert_called_once_with(["account_1", "account_2"])


@pytest.mark.anyio
async def test_get_wealthsimple_accounts_debug_and_dump():
    mock_gateway = AsyncMock()
    mock_gateway.get_accounts.return_value = []

    test_args = [
        "get_wealthsimple_accounts.py",
        "user@example.com",
        "--debug",
        "--dump",
        "/tmp/dump.json",
    ]
    with (
        patch.object(sys, "argv", test_args),
        patch(
            "src.account.commands.get_wealthsimple_accounts.wealthsimple_api_wrapper_factory",
            new_callable=AsyncMock,
            return_value=mock_gateway,
        ) as mock_factory,
        patch("src.account.commands.get_wealthsimple_accounts.rprint"),
    ):
        await main()

    mock_factory.assert_called_once_with(
        debug_api_responses=True,
        debug_dump_path="/tmp/dump.json",
    )
