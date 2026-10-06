# ruff: noqa: ARG001, PLR2004
"""Thin smoke tests for Stage 2 task wiring.

Behavioral assertions live in test_alert_evaluation_service.py.
These tests only verify the task delegates correctly to the service.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from src.config.settings import Settings
from src.market.alert_service import AlertEvaluationService
from src.market.repository import IntradayPriceRepository, PriceAlertRepository
from src.market.schema import AlertForEvaluation
from src.market.task import _check_and_dispatch_price_alerts
from src.observability import bootstrap_observability, reset_observability


@pytest.fixture(autouse=True)
def _cleanup_observability():
    yield
    reset_observability()


def _bootstrap_with_exporter(exporter: InMemorySpanExporter) -> None:
    bootstrap_observability(
        service_name="backend",
        settings=Settings(
            environment="test",
            deploy_id="deploy-abc123",
            service_version="1.2.3",
        ),
        span_processor=SimpleSpanProcessor(exporter),
    )


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    _bootstrap_with_exporter(exporter)
    return exporter


def _alert_evaluated_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return [
        span for span in exporter.get_finished_spans() if span.name == "alert.evaluated"
    ]


def _single_alert_event(
    exporter: InMemorySpanExporter,
) -> tuple[ReadableSpan, dict[str, Any]]:
    spans = _alert_evaluated_spans(exporter)
    assert len(spans) == 1, (
        f"expected exactly one alert.evaluated span, got {len(spans)}"
    )
    span = spans[0]
    assert span.attributes is not None
    return span, dict(span.attributes)


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
async def test_stage2_no_active_alerts_returns_early(span_exporter):
    """When there are no active alerts, the task returns early and emits one event."""
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

    # The early return still reports the (empty) run exactly once.
    span, attributes = _single_alert_event(span_exporter)
    assert attributes["event.name"] == "alert.evaluated"
    assert attributes["alerts_evaluated"] == 0
    assert attributes["alerts_triggered"] == 0
    assert attributes["outcome"] == "success"
    assert isinstance(attributes["duration_ms"], float)
    assert datetime.fromisoformat(str(attributes["run_at"])).tzinfo is not None
    assert span.status.status_code is StatusCode.UNSET


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


# --------------------------------------------------------------------------- #
# Wide event emission (F-OBS-T15)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_stage2_emits_single_alert_evaluated_event(span_exporter):
    """A normal run emits exactly one alert.evaluated event with counts."""
    sec_aapl = uuid4()
    sec_msft = uuid4()
    alert_aapl = _make_alert(alert_id=1, security_id=sec_aapl, security_symbol="AAPL")
    alert_msft = _make_alert(alert_id=2, security_id=sec_msft, security_symbol="MSFT")

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(
        return_value=[alert_aapl, alert_msft]
    )

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={sec_aapl: Decimal("155.00"), sec_msft: Decimal("100.00")}
    )

    alert_service = AsyncMock(spec=AlertEvaluationService)
    alert_service.evaluate = MagicMock(return_value=[alert_aapl])

    mock_container = _mock_container(alert_repo, intraday_repo, alert_service)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task"),
    ):
        await _check_and_dispatch_price_alerts()

    span, attributes = _single_alert_event(span_exporter)
    assert attributes["alerts_evaluated"] == 2
    assert attributes["alerts_triggered"] == 1
    assert attributes["outcome"] == "success"
    assert isinstance(attributes["duration_ms"], float)
    assert datetime.fromisoformat(str(attributes["run_at"])).tzinfo is not None
    assert span.status.status_code is StatusCode.UNSET

    outcomes = json.loads(str(attributes["symbol_outcomes"]))
    assert outcomes == {"AAPL": "triggered", "MSFT": "no_trigger"}


@pytest.mark.asyncio
async def test_stage2_symbol_outcomes_are_bounded(span_exporter):
    """symbol_outcomes stops at the cap and marks the mapping as truncated."""
    alerts = [
        _make_alert(alert_id=index, security_symbol=f"SYM{index:03d}")
        for index in range(60)
    ]

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=alerts)

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(return_value={})

    alert_service = AsyncMock(spec=AlertEvaluationService)
    alert_service.evaluate = MagicMock(return_value=[])

    mock_container = _mock_container(alert_repo, intraday_repo, alert_service)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task"),
    ):
        await _check_and_dispatch_price_alerts()

    _, attributes = _single_alert_event(span_exporter)
    assert attributes["alerts_evaluated"] == 60

    outcomes = json.loads(str(attributes["symbol_outcomes"]))
    assert outcomes["truncated"] is True
    assert len(outcomes) == 51
    assert outcomes["SYM000"] == "no_trigger"
    assert "SYM050" not in outcomes


@pytest.mark.asyncio
async def test_stage2_evaluation_failure_emits_error_event_and_reraises(span_exporter):
    """A failing evaluation emits one failure event and the exception propagates."""
    sec_id = uuid4()
    alert = _make_alert(security_id=sec_id)

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation = AsyncMock(return_value=[alert])

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(return_value={})

    alert_service = AsyncMock(spec=AlertEvaluationService)
    alert_service.evaluate = MagicMock(side_effect=RuntimeError("evaluation exploded"))

    mock_container = _mock_container(alert_repo, intraday_repo, alert_service)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.task.alert_email_dispatch_task"),
        pytest.raises(RuntimeError, match="evaluation exploded"),
    ):
        await _check_and_dispatch_price_alerts()

    span, attributes = _single_alert_event(span_exporter)
    assert attributes["outcome"] == "failure"
    assert attributes["error_slug"] == "alert_evaluation_failed"
    assert attributes["alerts_evaluated"] == 1
    assert attributes["alerts_triggered"] == 0
    assert span.status.status_code is StatusCode.ERROR
