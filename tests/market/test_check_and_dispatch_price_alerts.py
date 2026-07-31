# ruff: noqa: ARG001, PLR2004
"""Thin smoke tests for Stage 2 task wiring.

Behavioral assertions live in test_alert_evaluation_service.py.
These tests only verify the task delegates correctly to the service.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.market.alert_service import AlertEvaluationService
from src.market.repository import IntradayPriceRepository, PriceAlertRepository
from src.market.schema import AlertForEvaluation
from src.market.task import _check_and_dispatch_price_alerts


def _make_alert(
    *,
    alert_id: int = 1,
    security_id=None,
    security_symbol: str = "AAPL",
    target_price: Decimal = Decimal("150.00"),
    condition: str = "above",
) -> AlertForEvaluation:
    return AlertForEvaluation(
        alert_id=alert_id,
        security_id=security_id or uuid4(),
        security_symbol=security_symbol,
        security_name="Test Corp",
        user_id=uuid4(),
        target_price=target_price,
        condition=condition,
    )


def _mock_container(alert_repo, intraday_repo, alert_service):
    """Build a mock svcs container that returns the given services."""

    async def aget(t):
        if t is PriceAlertRepository:
            return alert_repo
        if t is IntradayPriceRepository:
            return intraday_repo
        if t is AlertEvaluationService:
            return alert_service
        return AsyncMock()

    mock_container = AsyncMock()
    mock_container.aget.side_effect = aget
    mock_container.__aenter__.return_value = mock_container
    return mock_container


@pytest.mark.asyncio
async def test_stage2_no_active_alerts_returns_early():
    """When there are no active alerts, the task returns early."""
    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[])
    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    alert_service = AsyncMock(spec=AlertEvaluationService)

    mock_container = _mock_container(alert_repo, intraday_repo, alert_service)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
    ):
        await _check_and_dispatch_price_alerts()

    alert_repo.get_active_alerts_for_evaluation.assert_awaited_once()
    # Intraday prices should NOT be fetched when there are no alerts
    intraday_repo.get_latest_intraday_close_by_security.assert_not_awaited()
    alert_service.evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_stage2_enqueues_one_per_triggered_alert():
    """Stage 2 enqueues one Stage 3 task per triggered alert returned by service."""
    sec_id = uuid4()
    alert = _make_alert(security_id=sec_id)

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[alert])

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={sec_id: Decimal("155.00")}
    )

    alert_service = AsyncMock(spec=AlertEvaluationService)
    alert_service.evaluate = MagicMock(return_value=[alert])

    mock_container = _mock_container(alert_repo, intraday_repo, alert_service)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task") as mock_dispatch,
    ):
        await _check_and_dispatch_price_alerts()

    # Service.evaluate was called with the alerts and latest prices
    alert_service.evaluate.assert_called_once()
    eval_args = alert_service.evaluate.call_args
    assert eval_args[0][0] == [alert]
    assert eval_args[0][1] == {sec_id: Decimal("155.00")}

    # One dispatch task enqueued per triggered alert
    mock_dispatch.assert_called_once()
    call_args = mock_dispatch.call_args
    assert call_args[0][0] == alert.alert_id
    assert isinstance(call_args[0][1], datetime)


@pytest.mark.asyncio
async def test_stage2_zero_dispatches_when_no_alerts_triggered():
    """Stage 2 enqueues zero Stage 3 tasks when service returns empty list."""
    sec_id = uuid4()
    alert = _make_alert(security_id=sec_id)

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[alert])

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={sec_id: Decimal("100.00")}
    )

    alert_service = AsyncMock(spec=AlertEvaluationService)
    alert_service.evaluate = MagicMock(return_value=[])

    mock_container = _mock_container(alert_repo, intraday_repo, alert_service)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task") as mock_dispatch,
    ):
        await _check_and_dispatch_price_alerts()

    mock_dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_stage2_enqueue_failure_isolated():
    """If dispatching one alert raises, the rest are still processed."""
    alert_1 = _make_alert(alert_id=1)
    alert_2 = _make_alert(alert_id=2)

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(
        return_value=[alert_1, alert_2]
    )

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(return_value={})

    alert_service = AsyncMock(spec=AlertEvaluationService)
    alert_service.evaluate = MagicMock(return_value=[alert_1, alert_2])

    mock_container = _mock_container(alert_repo, intraday_repo, alert_service)

    dispatch_call_count = 0

    def dispatch_side_effect(*args, **kwargs):
        nonlocal dispatch_call_count
        dispatch_call_count += 1
        if dispatch_call_count == 1:
            msg = "dispatch error"
            raise RuntimeError(msg)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch(
            "src.market.task.alert_email_dispatch_task",
            side_effect=dispatch_side_effect,
        ),
    ):
        await _check_and_dispatch_price_alerts()

    # Both alerts triggered and dispatch was attempted for both
    assert dispatch_call_count == 2


@pytest.mark.asyncio
async def test_stage2_no_registry_returns_early():
    """When huey.svcs_registry is None, the task returns without error."""
    with patch("src.market.task.huey.svcs_registry", None):
        await _check_and_dispatch_price_alerts()
    # Should not raise
