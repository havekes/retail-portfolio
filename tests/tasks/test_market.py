import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

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

    mock_container = AsyncMock()
    mock_container.aget.return_value = mock_market_service
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.recalculate_all_account_totals_task") as mock_recalc,
        patch("src.market.task.check_and_dispatch_price_alerts") as mock_check,
    ):
        await _hourly_intraday_price_update()

    mock_market_service.update_intraday_prices_for_all_securities.assert_awaited_once()
    mock_recalc.assert_called_once()
    mock_check.assert_called_once()


def test_worker_command_enables_periodic_scheduling():
    """The worker consumer command in docker-compose.yml must include --periodic.

    Without --periodic, Huey ignores periodic task schedules entirely — daily
    and hourly price updates never fire. This is the regression that caused
    issue #140 (intraday prices table empty because the hourly task never ran).
    """
    with Path("docker-compose.yml").open() as f:
        compose = yaml.safe_load(f)
    cmd = compose["services"]["worker"]["command"]
    assert "huey_consumer" in cmd, "worker consumer command must invoke huey_consumer"
    assert "--periodic" in cmd, (
        "worker consumer command must include --periodic or periodic tasks "
        "(daily/hourly price updates) will never be scheduled. See #140."
    )


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
        patch("src.market.task.recalculate_all_account_totals_task"),
        patch("src.market.task.check_and_dispatch_price_alerts"),
    ):
        await _hourly_intraday_price_update()

        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("3" in call and "1" in call for call in log_calls)


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_enqueues_account_totals_task():
    """Hourly intraday price update enqueues recalculate_all_account_totals_task."""
    mock_market_service = AsyncMock(spec=MarketService)
    mock_market_service.update_intraday_prices_for_all_securities.return_value = {
        "success": 1,
        "failure": 0,
    }

    mock_container = AsyncMock()
    mock_container.aget.return_value = mock_market_service
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.recalculate_all_account_totals_task") as mock_recalc,
        patch("src.market.task.check_and_dispatch_price_alerts"),
    ):
        await _hourly_intraday_price_update()

        mock_recalc.assert_called_once()


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_account_totals_enqueue_failure_doesnt_abort():
    """If recalculate_all_account_totals_task raises, Stage 2 check_and_dispatch is still called."""
    mock_market_service = AsyncMock(spec=MarketService)
    mock_market_service.update_intraday_prices_for_all_securities.return_value = {
        "success": 1,
        "failure": 0,
    }

    mock_container = AsyncMock()
    mock_container.aget.return_value = mock_market_service
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch(
            "src.market.task.recalculate_all_account_totals_task",
            side_effect=RuntimeError("recalc enqueue failed"),
        ),
        patch("src.market.task.check_and_dispatch_price_alerts") as mock_check,
        patch("src.market.task.logger") as mock_logger,
    ):
        await _hourly_intraday_price_update()

        mock_check.assert_called_once()
        mock_logger.exception.assert_called_once_with(
            "Failed to enqueue recalculate_all_account_totals_task"
        )


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


def test_hourly_intraday_price_update_in_huey_periodic_tasks():
    """The hourly intraday task must be registered as a periodic task on the Huey instance.

    This test ensures the task appears in huey._registry.periodic_tasks — if it's
    missing, the worker will never schedule it even with --periodic, and intraday
    prices stay empty. See issue #140.
    """
    task_names = {item.name for item in huey._registry.periodic_tasks}
    assert "hourly_intraday_price_update" in task_names, (
        "hourly_intraday_price_update is not in huey._registry.periodic_tasks; "
        "the worker will never schedule it. Check that @huey.periodic_task "
        "decorator is used and src.market.task is imported where Huey is defined."
    )


def test_daily_price_update_in_huey_periodic_tasks():
    """The daily price update task must be registered as a periodic task."""
    task_names = {item.name for item in huey._registry.periodic_tasks}
    assert "daily_price_update" in task_names, (
        "daily_price_update is not in huey._registry.periodic_tasks"
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


# -- Stage 1 enqueue isolation --


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_enqueues_check_and_dispatch():
    """Stage 1 enqueues check_and_dispatch_price_alerts at the end."""
    mock_market_service = AsyncMock()
    mock_market_service.update_intraday_prices_for_all_securities.return_value = {
        "success": 1,
        "failure": 0,
    }

    mock_container = AsyncMock()
    mock_container.aget.return_value = mock_market_service
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.recalculate_all_account_totals_task"),
        patch("src.market.task.check_and_dispatch_price_alerts") as mock_check,
    ):
        await _hourly_intraday_price_update()

    mock_check.assert_called_once()


@pytest.mark.asyncio
async def test_hourly_intraday_price_update_check_dispatch_failure_doesnt_abort():
    """If check_and_dispatch_price_alerts raises, Stage 1 still completes."""
    mock_market_service = AsyncMock()
    mock_market_service.update_intraday_prices_for_all_securities.return_value = {
        "success": 1,
        "failure": 0,
    }

    mock_container = AsyncMock()
    mock_container.aget.return_value = mock_market_service
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.recalculate_all_account_totals_task"),
        patch(
            "src.market.task.check_and_dispatch_price_alerts",
            side_effect=RuntimeError("enqueue failed"),
        ),
    ):
        # Should NOT raise — the try/except isolates the enqueue
        await _hourly_intraday_price_update()

    # Market service was called despite enqueue failure
    mock_market_service.update_intraday_prices_for_all_securities.assert_awaited_once()
