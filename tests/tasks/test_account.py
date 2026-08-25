import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from stockholm import Currency, Money

from src.account.api_types import AccountTotals
from src.account.schema import AccountSchema
from src.account.service.account import AccountService
from src.account.service.position import PositionService
from src.account.task import (
    _recalculate_all_account_totals,
    recalculate_all_account_totals_task,
)
from src.worker import huey


def test_recalculate_all_account_totals_task_in_huey_tasks():
    """Verify task is registered in Huey's task registry."""
    assert hasattr(recalculate_all_account_totals_task, "orig_fn") or callable(
        recalculate_all_account_totals_task
    )
    assert (
        "src.account.task.recalculate_all_account_totals_task"
        in huey._registry._registry
    )


def test_recalculate_all_account_totals_task_calls_async_logic():
    """Verify synchronous invocation under huey.immediate triggers asyncio.run."""
    huey.immediate = True
    try:
        with patch("src.account.task.asyncio.run") as mock_run:
            recalculate_all_account_totals_task()
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert asyncio.iscoroutine(args[0])
            args[0].close()
    finally:
        huey.immediate = False


@pytest.mark.asyncio
async def test_recalculate_all_account_totals_success():
    """Verify active accounts are calculated and broadcast, inactive accounts are skipped."""
    active_account = MagicMock(spec=AccountSchema)
    active_account.id = uuid4()
    active_account.user_id = uuid4()
    active_account.currency = Currency.USD
    active_account.is_active = True

    inactive_account = MagicMock(spec=AccountSchema)
    inactive_account.id = uuid4()
    inactive_account.user_id = uuid4()
    inactive_account.currency = Currency.USD
    inactive_account.is_active = False

    mock_account_service = AsyncMock(spec=AccountService)
    mock_account_service.get_all_accounts.return_value = [
        active_account,
        inactive_account,
    ]

    fake_totals = AccountTotals(
        cost=Money(500, Currency.USD),
        value=Money(650, Currency.USD),
    )
    mock_position_service = AsyncMock(spec=PositionService)
    mock_position_service.get_total_for_account.return_value = fake_totals

    async def mock_aget(service_type):
        if service_type is AccountService:
            return mock_account_service
        if service_type is PositionService:
            return mock_position_service
        return AsyncMock()

    mock_container = AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.account.task.huey.svcs_registry", MagicMock()),
        patch("src.account.task.Container", return_value=mock_container),
        patch("src.account.task.ws_manager") as mock_ws_manager,
    ):
        mock_ws_manager.send_personal_message = AsyncMock()
        await _recalculate_all_account_totals()

        mock_account_service.get_all_accounts.assert_awaited_once()
        mock_position_service.get_total_for_account.assert_awaited_once_with(
            active_account.id, active_account.currency
        )
        mock_ws_manager.send_personal_message.assert_awaited_once()
        call_args = mock_ws_manager.send_personal_message.call_args
        payload, target_user_id = call_args[0]
        assert target_user_id == active_account.user_id
        assert payload["type"] == "account_totals_updated"
        assert payload["account_id"] == str(active_account.id)
        assert payload["totals"]["cost"]["value"] == "500.00 USD"
        assert payload["totals"]["value"]["value"] == "650.00 USD"


@pytest.mark.asyncio
async def test_recalculate_all_account_totals_per_account_error_resilience():
    """Verify an error calculating one account does not stop processing for others."""
    account1 = MagicMock(spec=AccountSchema)
    account1.id = uuid4()
    account1.user_id = uuid4()
    account1.currency = Currency.USD
    account1.is_active = True

    account2 = MagicMock(spec=AccountSchema)
    account2.id = uuid4()
    account2.user_id = uuid4()
    account2.currency = Currency.CAD
    account2.is_active = True

    mock_account_service = AsyncMock(spec=AccountService)
    mock_account_service.get_all_accounts.return_value = [account1, account2]

    mock_position_service = AsyncMock(spec=PositionService)
    totals2 = AccountTotals(
        cost=Money(100, Currency.CAD),
        value=Money(150, Currency.CAD),
    )

    async def mock_get_total(account_id, currency):
        if account_id == account1.id:
            raise RuntimeError("Database connection timeout")
        return totals2

    mock_position_service.get_total_for_account.side_effect = mock_get_total

    async def mock_aget(service_type):
        if service_type is AccountService:
            return mock_account_service
        if service_type is PositionService:
            return mock_position_service
        return AsyncMock()

    mock_container = AsyncMock()
    mock_container.aget.side_effect = mock_aget
    mock_container.__aenter__.return_value = mock_container

    with (
        patch("src.account.task.huey.svcs_registry", MagicMock()),
        patch("src.account.task.Container", return_value=mock_container),
        patch("src.account.task.ws_manager") as mock_ws_manager,
        patch("src.account.task.logger") as mock_logger,
    ):
        mock_ws_manager.send_personal_message = AsyncMock()
        await _recalculate_all_account_totals()

        assert mock_position_service.get_total_for_account.await_count == 2
        mock_ws_manager.send_personal_message.assert_awaited_once()
        payload, target_user_id = mock_ws_manager.send_personal_message.call_args[0]
        assert target_user_id == account2.user_id
        assert payload["account_id"] == str(account2.id)
        mock_logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_recalculate_all_account_totals_raises_if_no_registry():
    """Verify RuntimeError is raised when huey.svcs_registry is None."""
    with (
        patch("src.account.task.huey.svcs_registry", None),
        pytest.raises(RuntimeError, match="Worker registry not initialized"),
    ):
        await _recalculate_all_account_totals()
