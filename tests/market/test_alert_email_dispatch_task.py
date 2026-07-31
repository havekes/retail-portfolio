# ruff: noqa: PLR2004
"""Thin smoke tests for Stage 3 task wiring.

Behavioral assertions live in test_alert_evaluation_service.py.
These tests only verify the task delegates correctly to the service.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.market.alert_service import AlertEvaluationService
from src.market.task import _alert_email_dispatch, alert_email_dispatch_task


def _mock_container(alert_service):
    """Build a mock svcs container that returns the alert service."""

    async def aget(t):
        if t is AlertEvaluationService:
            return alert_service
        return AsyncMock()

    mock_container = AsyncMock()
    mock_container.aget.side_effect = aget
    mock_container.__aenter__.return_value = mock_container
    return mock_container


@pytest.mark.asyncio
async def test_stage3_delegates_to_service():
    """Stage 3 resolves AlertEvaluationService and delegates dispatch."""
    run_ts = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)

    alert_service = AsyncMock(spec=AlertEvaluationService)
    alert_service.dispatch_alert_email = AsyncMock()

    mock_container = _mock_container(alert_service)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
    ):
        await _alert_email_dispatch(42, run_ts)

    alert_service.dispatch_alert_email.assert_awaited_once_with(42, run_ts)


@pytest.mark.asyncio
async def test_stage3_no_registry_returns_early():
    """When huey.svcs_registry is None, the task returns without error."""
    with patch("src.market.task.huey.svcs_registry", None):
        await _alert_email_dispatch(1, datetime.now(UTC))
    # Should not raise


def test_stage3_decorator_has_retries():
    """The alert_email_dispatch_task decorator specifies retries=3."""
    assert alert_email_dispatch_task.settings["default_retries"] == 3
