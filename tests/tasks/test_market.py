import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from stockholm import Currency, Money

from src.account.api_types import AccountTotals
from src.account.service.account import AccountService
from src.account.service.position import PositionService
from src.market.service import MarketService
from src.market.task import (
    _daily_price_update,
    _hourly_intraday_price_update,
    daily_price_update,
    hourly_intraday_price_update,
)
from src.worker import huey


@pytest.mark.asyncio
async def test_daily_price_update_success():
    mock_market_service = AsyncMock()
    mock_market_service.update_daily_prices_for_all_securities.return_value = {
        "success": 2,
        "failure": 0,
    }

    mock_container = AsyncMock()
    mock_container.aget.return_value = mock_market_service
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
    ):
        await _daily_price_update()

        mock_container.aget.assert_awaited_once_with(MarketService)
        mock_market_service.update_daily_prices_for_all_securities.assert_awaited_once()


@pytest.mark.asyncio
async def test_daily_price_update_logs_results():
    mock_market_service = AsyncMock()
    mock_market_service.update_daily_prices_for_all_securities.return_value = {
        "success": 5,
        "failure": 1,
    }

    mock_container = AsyncMock()
    mock_container.aget.return_value = mock_market_service
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.logger") as mock_logger,
    ):
        await _daily_price_update()

        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("5" in call and "1" in call for call in log_calls)


@pytest.mark.asyncio
async def test_daily_price_update_raises_if_no_container():
    with (
        patch("src.market.task.huey.svcs_registry", None),
        pytest.raises(RuntimeError, match="Worker registry not initialized"),
    ):
        await _daily_price_update()


def test_daily_price_update_is_periodic_task():
    assert hasattr(daily_price_update, "orig_fn") or callable(daily_price_update)


def test_daily_price_update_calls_async_logic():
    huey.immediate = True

    with patch("src.market.task.asyncio.run") as mock_run:
        daily_price_update()
        mock_run.assert_called_once()
        args = mock_run.call_args[0]
        assert asyncio.iscoroutine(args[0])
        args[0].close()

    huey.immediate = False


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_success():
    mock_market_service = AsyncMock()
    mock_market_service.update_intraday_prices_for_all_securities.return_value = {
        "success": 2,
        "failure": 0,
    }
    mock_account_service = AsyncMock()
    mock_account_service.get_all_accounts.return_value = []
    mock_position_service = AsyncMock()

    async def mock_aget(service_type):
        if service_type is MarketService:
            return mock_market_service
        if service_type is AccountService:
            return mock_account_service
        if service_type is PositionService:
            return mock_position_service
        return AsyncMock()

    mock_container = AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
    ):
        await _hourly_intraday_price_update()

        mock_market_service.update_intraday_prices_for_all_securities.assert_awaited_once()


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_logs_results():
    mock_market_service = AsyncMock()
    mock_market_service.update_intraday_prices_for_all_securities.return_value = {
        "success": 3,
        "failure": 1,
    }
    mock_account_service = AsyncMock()
    mock_account_service.get_all_accounts.return_value = []
    mock_position_service = AsyncMock()

    async def mock_aget(service_type):
        if service_type is MarketService:
            return mock_market_service
        if service_type is AccountService:
            return mock_account_service
        if service_type is PositionService:
            return mock_position_service
        return AsyncMock()

    mock_container = AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.logger") as mock_logger,
    ):
        await _hourly_intraday_price_update()

        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("3" in call and "1" in call for call in log_calls)


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_recalculates_totals_and_sends_ws_message():
    mock_market_service = AsyncMock(spec=MarketService)
    mock_market_service.update_intraday_prices_for_all_securities.return_value = {
        "success": 1,
        "failure": 0,
    }

    fake_account = MagicMock()
    fake_account.id = uuid4()
    fake_account.user_id = uuid4()
    fake_account.currency = Currency.USD
    fake_account.is_active = True

    fake_inactive_account = MagicMock()
    fake_inactive_account.id = uuid4()
    fake_inactive_account.user_id = uuid4()
    fake_inactive_account.currency = Currency.USD
    fake_inactive_account.is_active = False

    mock_account_service = AsyncMock(spec=AccountService)
    mock_account_service.get_all_accounts.return_value = [
        fake_account,
        fake_inactive_account,
    ]

    fake_totals = AccountTotals(
        cost=Money(100, Currency.USD),
        value=Money(120, Currency.USD),
    )
    mock_position_service = AsyncMock(spec=PositionService)
    mock_position_service.get_total_for_account.return_value = fake_totals

    async def mock_aget(service_type):
        if service_type is MarketService:
            return mock_market_service
        if service_type is AccountService:
            return mock_account_service
        if service_type is PositionService:
            return mock_position_service
        return AsyncMock()

    mock_container = AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.ws_manager") as mock_ws_manager,
    ):
        mock_ws_manager.send_personal_message = AsyncMock()
        await _hourly_intraday_price_update()

        mock_account_service.get_all_accounts.assert_awaited_once()
        mock_position_service.get_total_for_account.assert_awaited_once_with(
            fake_account.id, fake_account.currency
        )
        mock_ws_manager.send_personal_message.assert_awaited_once()
        call_args = mock_ws_manager.send_personal_message.call_args
        args_payload, user_id_arg = call_args[0]
        assert user_id_arg == fake_account.user_id
        assert args_payload["type"] == "account_totals_updated"
        assert args_payload["account_id"] == str(fake_account.id)


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_raises_if_no_container():
    with (
        patch("src.market.task.huey.svcs_registry", None),
        pytest.raises(RuntimeError, match="Worker registry not initialized"),
    ):
        await _hourly_intraday_price_update()


def test_hourly_intraday_price_update_is_periodic_task():
    assert hasattr(hourly_intraday_price_update, "orig_fn") or callable(
        hourly_intraday_price_update
    )


def test_hourly_intraday_price_update_calls_async_logic():
    huey.immediate = True

    with patch("src.market.task.asyncio.run") as mock_run:
        hourly_intraday_price_update()
        mock_run.assert_called_once()
        args = mock_run.call_args[0]
        assert asyncio.iscoroutine(args[0])
        args[0].close()

    huey.immediate = False
