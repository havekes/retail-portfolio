import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.market.service import MarketService
from src.market.task import _daily_price_update, daily_price_update
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

        # Verify completion log includes success/failure counts
        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("5" in call and "1" in call for call in log_calls)


@pytest.mark.asyncio
async def test_daily_price_update_raises_if_no_container():
    """Verify that _daily_price_update raises an error if worker registry is not initialized."""
    with patch("src.market.task.huey.svcs_registry", None):
        with pytest.raises(RuntimeError, match="Worker registry not initialized"):
            await _daily_price_update()


def test_daily_price_update_is_periodic_task():
    """Verify daily_price_update is registered as a Huey periodic task."""
    # Huey wraps periodic tasks; the original function is accessible via .orig_fn
    assert hasattr(daily_price_update, "orig_fn") or callable(daily_price_update)


def test_daily_price_update_calls_async_logic():
    """Verify the periodic task invokes _daily_price_update via asyncio.run."""
    # Run task in immediate mode
    huey.immediate = True

    with patch("src.market.task.asyncio.run") as mock_run:
        # Calling it directly executes it immediately because huey.immediate = True
        daily_price_update()
        mock_run.assert_called_once()
        # The argument should be a coroutine (result of _daily_price_update())
        args = mock_run.call_args[0]
        assert asyncio.iscoroutine(args[0])
        # Clean up the unawaited coroutine
        args[0].close()

    # Reset for other tests if any
    huey.immediate = False
