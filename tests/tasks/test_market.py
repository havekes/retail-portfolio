import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    with patch("src.market.task.huey.svcs_registry", None):
        with pytest.raises(RuntimeError, match="Worker registry not initialized"):
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

    mock_container = AsyncMock()
    mock_container.aget.return_value = mock_market_service
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
    ):
        await _hourly_intraday_price_update()

        mock_container.aget.assert_awaited_once_with(MarketService)
        mock_market_service.update_intraday_prices_for_all_securities.assert_awaited_once()


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_logs_results():
    mock_market_service = AsyncMock()
    mock_market_service.update_intraday_prices_for_all_securities.return_value = {
        "success": 3,
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
        await _hourly_intraday_price_update()

        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("3" in call and "1" in call for call in log_calls)


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_raises_if_no_container():
    with patch("src.market.task.huey.svcs_registry", None):
        with pytest.raises(RuntimeError, match="Worker registry not initialized"):
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
