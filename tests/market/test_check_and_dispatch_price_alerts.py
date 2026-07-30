# ruff: noqa: ARG001, PLR2004
"""Tests for Stage 2: check_and_dispatch_price_alerts task."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

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


def _mock_container(
    alert_repo: PriceAlertRepository,
    intraday_repo: IntradayPriceRepository,
):
    """Build a mock svcs container that returns the given repos."""
    mock_container = AsyncMock()
    mock_container.aget.side_effect = lambda t: (
        alert_repo if t is PriceAlertRepository else intraday_repo
    )
    mock_container.__aenter__.return_value = mock_container
    return mock_container


@pytest.mark.asyncio
async def test_stage2_no_active_alerts():
    """When there are no active alerts, the task returns early."""
    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[])
    intraday_repo = AsyncMock(spec=IntradayPriceRepository)

    mock_container = _mock_container(alert_repo, intraday_repo)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
    ):
        await _check_and_dispatch_price_alerts()

    alert_repo.get_active_alerts_for_evaluation.assert_awaited_once()
    # Intraday prices should NOT be fetched when there are no alerts
    intraday_repo.get_latest_intraday_close_by_security.assert_not_awaited()


@pytest.mark.asyncio
async def test_stage2_above_condition_triggered():
    """Alert fires when latest_price >= target and condition is 'above'."""
    sec_id = uuid4()
    alert = _make_alert(
        security_id=sec_id,
        target_price=Decimal("150.00"),
        condition="above",
    )

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[alert])

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={sec_id: Decimal("155.00")}
    )

    mock_container = _mock_container(alert_repo, intraday_repo)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task") as mock_dispatch,
    ):
        await _check_and_dispatch_price_alerts()

    mock_dispatch.assert_called_once()
    call_args = mock_dispatch.call_args
    assert call_args[0][0] == alert.alert_id
    assert isinstance(call_args[0][1], datetime)


@pytest.mark.asyncio
async def test_stage2_below_condition_triggered():
    """Alert fires when latest_price <= target and condition is 'below'."""
    sec_id = uuid4()
    alert = _make_alert(
        security_id=sec_id,
        target_price=Decimal("150.00"),
        condition="below",
    )

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[alert])

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={sec_id: Decimal("145.00")}
    )

    mock_container = _mock_container(alert_repo, intraday_repo)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task") as mock_dispatch,
    ):
        await _check_and_dispatch_price_alerts()

    mock_dispatch.assert_called_once()


@pytest.mark.asyncio
async def test_stage2_boundary_inclusive_above():
    """Price exactly at target triggers 'above' (inclusive boundary)."""
    sec_id = uuid4()
    alert = _make_alert(
        security_id=sec_id,
        target_price=Decimal("150.00"),
        condition="above",
    )

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[alert])

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={sec_id: Decimal("150.00")}
    )

    mock_container = _mock_container(alert_repo, intraday_repo)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task") as mock_dispatch,
    ):
        await _check_and_dispatch_price_alerts()

    mock_dispatch.assert_called_once()


@pytest.mark.asyncio
async def test_stage2_boundary_inclusive_below():
    """Price exactly at target triggers 'below' (inclusive boundary)."""
    sec_id = uuid4()
    alert = _make_alert(
        security_id=sec_id,
        target_price=Decimal("150.00"),
        condition="below",
    )

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[alert])

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={sec_id: Decimal("150.00")}
    )

    mock_container = _mock_container(alert_repo, intraday_repo)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task") as mock_dispatch,
    ):
        await _check_and_dispatch_price_alerts()

    mock_dispatch.assert_called_once()


@pytest.mark.asyncio
async def test_stage2_not_triggered_when_price_not_reached():
    """Alert does NOT fire when price hasn't crossed the threshold."""
    sec_id = uuid4()
    alert = _make_alert(
        security_id=sec_id,
        target_price=Decimal("200.00"),
        condition="above",
    )

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[alert])

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={sec_id: Decimal("150.00")}
    )

    mock_container = _mock_container(alert_repo, intraday_repo)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task") as mock_dispatch,
    ):
        await _check_and_dispatch_price_alerts()

    mock_dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_stage2_no_price_for_security_skips():
    """Alert with no intraday price for its security is skipped."""
    sec_id = uuid4()
    alert = _make_alert(
        security_id=sec_id,
        target_price=Decimal("150.00"),
        condition="above",
    )

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[alert])

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={}
    )

    mock_container = _mock_container(alert_repo, intraday_repo)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task") as mock_dispatch,
    ):
        await _check_and_dispatch_price_alerts()

    mock_dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_stage2_single_alert_dispatch_failure_doesnt_abort_others():
    """If dispatching one alert raises, the rest are still processed."""
    sec_id_1 = uuid4()
    sec_id_2 = uuid4()
    alert_1 = _make_alert(
        alert_id=1,
        security_id=sec_id_1,
        target_price=Decimal("150.00"),
        condition="above",
    )
    alert_2 = _make_alert(
        alert_id=2,
        security_id=sec_id_2,
        target_price=Decimal("150.00"),
        condition="above",
    )

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(
        return_value=[alert_1, alert_2]
    )

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={
            sec_id_1: Decimal("155.00"),
            sec_id_2: Decimal("160.00"),
        }
    )

    mock_container = _mock_container(alert_repo, intraday_repo)

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
    with (
        patch("src.market.task.huey.svcs_registry", None),
    ):
        await _check_and_dispatch_price_alerts()
    # Should not raise
