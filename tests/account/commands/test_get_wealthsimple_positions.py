import sys
from unittest.mock import AsyncMock, patch

import pytest

from src.account.commands.get_wealthsimple_positions import main


@pytest.mark.anyio
async def test_get_wealthsimple_positions_default():
    mock_gateway = AsyncMock()
    mock_gateway.get_positions_by_account.return_value = ["pos_1", "pos_2"]

    test_args = ["get_wealthsimple_positions.py", "user@example.com", "acc_123"]
    with (
        patch.object(sys, "argv", test_args),
        patch(
            "src.account.commands.get_wealthsimple_positions.wealthsimple_api_wrapper_factory",
            new_callable=AsyncMock,
            return_value=mock_gateway,
        ) as mock_factory,
        patch("src.account.commands.get_wealthsimple_positions.rprint") as mock_rprint,
    ):
        await main()

    mock_factory.assert_called_once_with(debug_api_responses=False, debug_dump_path=None)
    mock_gateway.get_positions_by_account.assert_called_once()
    user_arg, acc_id_arg = mock_gateway.get_positions_by_account.call_args[0]
    assert user_arg.external_user_id == "user@example.com"
    assert acc_id_arg == "acc_123"
    mock_rprint.assert_called_once_with(["pos_1", "pos_2"])


@pytest.mark.anyio
async def test_get_wealthsimple_positions_debug():
    mock_gateway = AsyncMock()
    mock_gateway.get_positions_by_account.return_value = []

    test_args = [
        "get_wealthsimple_positions.py",
        "user@example.com",
        "acc_123",
        "--debug",
    ]
    with (
        patch.object(sys, "argv", test_args),
        patch(
            "src.account.commands.get_wealthsimple_positions.wealthsimple_api_wrapper_factory",
            new_callable=AsyncMock,
            return_value=mock_gateway,
        ) as mock_factory,
        patch("src.account.commands.get_wealthsimple_positions.rprint"),
    ):
        await main()

    mock_factory.assert_called_once_with(
        debug_api_responses=True,
        debug_dump_path=None,
    )
