import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.commands.scheduler import run_update, main


@pytest.mark.asyncio
async def test_run_update_success():
    mock_market_service = AsyncMock()
    mock_market_service.update_daily_prices_for_all_securities.return_value = {
        "success": 2,
        "failure": 0,
    }

    mock_container = AsyncMock()
    mock_container.__aenter__.return_value = mock_container
    mock_container.aget.return_value = mock_market_service

    with patch(
        "src.commands.scheduler.Registry"
    ) as mock_registry, patch(
        "src.commands.scheduler.register_services"
    ) as mock_register, patch(
        "src.commands.scheduler.Container", return_value=mock_container
    ) as mock_container_class:
        await run_update()

        mock_registry.assert_called_once()
        mock_register.assert_called_once()
        mock_container_class.assert_called_once()
        mock_market_service.update_daily_prices_for_all_securities.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.commands.scheduler.AsyncIOScheduler")
@patch("src.commands.scheduler.asyncio.Event")
async def test_main_starts_scheduler(mock_event, mock_scheduler_class):
    mock_scheduler = MagicMock()
    mock_scheduler_class.return_value = mock_scheduler

    mock_event_instance = AsyncMock()
    mock_event.return_value = mock_event_instance

    await main()

    mock_scheduler_class.assert_called_once()
    mock_scheduler.add_job.assert_called_once()
    mock_scheduler.start.assert_called_once()
    mock_event_instance.wait.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.commands.scheduler.AsyncIOScheduler")
@patch("src.commands.scheduler.asyncio.Event")
async def test_main_handles_shutdown(mock_event, mock_scheduler_class):
    mock_scheduler = MagicMock()
    mock_scheduler_class.return_value = mock_scheduler

    mock_event_instance = AsyncMock()
    mock_event_instance.wait.side_effect = KeyboardInterrupt
    mock_event.return_value = mock_event_instance

    await main()

    mock_scheduler.shutdown.assert_called_once()
