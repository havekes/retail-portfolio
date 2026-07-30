# ruff: noqa: PLR0913
"""Tests for Stage 3: alert_email_dispatch_task (send email then mark triggered)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.auth.repository import UserRepository
from src.core.email import EmailService, PriceAlertEmailData
from src.market.repository import (
    IntradayPriceRepository,
    PriceAlertRepository,
    SecurityRepository,
)
from src.market.schema import PriceAlertRead, SecuritySchema
from src.market.task import _alert_email_dispatch


def _make_alert(
    *,
    alert_id: int = 1,
    security_id=None,
    user_id=None,
    target_price: Decimal = Decimal("150.00"),
    condition: str = "above",
    triggered_at=None,
) -> PriceAlertRead:
    return PriceAlertRead(
        id=alert_id,
        security_id=security_id or uuid4(),
        user_id=user_id or uuid4(),
        target_price=target_price,
        condition=condition,
        triggered_at=triggered_at,
        created_at=datetime.now(UTC),
    )


def _make_security(*, symbol: str = "AAPL", name: str = "Apple Inc"):
    sec_id = uuid4()
    return SecuritySchema(
        id=sec_id,
        symbol=symbol,
        name=name,
        exchange="NASDAQ",
        currency="USD",
        isin=None,
        is_active=True,
        updated_at=datetime.now(UTC),
    )


def _mock_container(alert_repo, security_repo, user_repo, email_service, intraday_repo):
    """Build a mock svcs container returning the given services."""

    async def aget(cls):
        if cls is PriceAlertRepository:
            return alert_repo
        if cls is SecurityRepository:
            return security_repo
        if cls is UserRepository:
            return user_repo
        if cls is EmailService:
            return email_service
        if cls is IntradayPriceRepository:
            return intraday_repo
        return AsyncMock()

    mock_container = AsyncMock()
    mock_container.aget.side_effect = aget
    mock_container.__aenter__.return_value = mock_container
    return mock_container


# -- Idempotency guard --


@pytest.mark.asyncio
async def test_stage3_already_triggered_is_noop():
    """If alert.triggered_at is not None, dispatch is a no-op."""
    alert = _make_alert(triggered_at=datetime.now(UTC))

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_by_id = AsyncMock(return_value=alert)

    mc = _mock_container(alert_repo, AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mc),
    ):
        await _alert_email_dispatch(alert.id, datetime.now(UTC))

    alert_repo.get_by_id.assert_awaited_once()
    # mark_triggered must NOT be called
    alert_repo.mark_triggered.assert_not_awaited()


@pytest.mark.asyncio
async def test_stage3_alert_not_found_is_noop():
    """If alert is None (deleted), dispatch is a no-op."""
    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_by_id = AsyncMock(return_value=None)

    mc = _mock_container(alert_repo, AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mc),
    ):
        await _alert_email_dispatch(999, datetime.now(UTC))

    alert_repo.mark_triggered.assert_not_awaited()


# -- Happy path --


@pytest.mark.asyncio
async def test_stage3_sends_email_and_marks_triggered():
    """Full happy path: fetch alert → send email → mark triggered."""
    security = _make_security(symbol="TSLA", name="Tesla")
    alert = _make_alert(
        security_id=security.id,
        target_price=Decimal("200.00"),
        condition="above",
    )
    user = MagicMock()
    user.email = "trader@example.com"

    run_ts = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)
    latest_price = Decimal("205.00")

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_by_id = AsyncMock(return_value=alert)

    security_repo = AsyncMock(spec=SecurityRepository)
    security_repo.get_by_id_or_fail = AsyncMock(return_value=security)

    user_repo = AsyncMock(spec=UserRepository)
    user_repo.get_by_id = AsyncMock(return_value=user)

    email_service = MagicMock(spec=EmailService)
    email_service.send_price_alert_email = MagicMock()

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={security.id: latest_price}
    )

    mc = _mock_container(
        alert_repo, security_repo, user_repo, email_service, intraday_repo
    )

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mc),
        patch(
            "src.market.task.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
        ),
    ):
        await _alert_email_dispatch(alert.id, run_ts)

    # Email was sent with correct params
    expected_alert = PriceAlertEmailData(
        security_id=alert.security_id,
        security_symbol=security.symbol,
        security_name=security.name,
        condition=alert.condition,
        target_price=alert.target_price,
        latest_price=latest_price,
    )
    email_service.send_price_alert_email.assert_called_once_with(
        recipient=user.email,
        alert=expected_alert,
    )

    # Alert was marked triggered with the run_ts
    alert_repo.mark_triggered.assert_called_once_with(alert.id, run_ts)


# -- Missing security --


@pytest.mark.asyncio
async def test_stage3_security_missing_skips():
    """If security lookup fails, dispatch is skipped (no mark_triggered)."""
    security_id = uuid4()
    alert = _make_alert(security_id=security_id)

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_by_id = AsyncMock(return_value=alert)

    security_repo = AsyncMock(spec=SecurityRepository)
    security_repo.get_by_id_or_fail = AsyncMock(side_effect=Exception("not found"))

    mc = _mock_container(
        alert_repo, security_repo, AsyncMock(), AsyncMock(), AsyncMock()
    )

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mc),
    ):
        await _alert_email_dispatch(alert.id, datetime.now(UTC))

    alert_repo.mark_triggered.assert_not_awaited()


# -- Missing user --


@pytest.mark.asyncio
async def test_stage3_user_missing_skips():
    """If user lookup returns None, dispatch is skipped."""
    security = _make_security()
    alert = _make_alert(security_id=security.id)

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_by_id = AsyncMock(return_value=alert)

    security_repo = AsyncMock(spec=SecurityRepository)
    security_repo.get_by_id_or_fail = AsyncMock(return_value=security)

    user_repo = AsyncMock(spec=UserRepository)
    user_repo.get_by_id = AsyncMock(return_value=None)

    mc = _mock_container(alert_repo, security_repo, user_repo, AsyncMock(), AsyncMock())

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mc),
    ):
        await _alert_email_dispatch(alert.id, datetime.now(UTC))

    alert_repo.mark_triggered.assert_not_awaited()


# -- No price at dispatch --


@pytest.mark.asyncio
async def test_stage3_no_intraday_price_at_dispatch_skips():
    """If no intraday price exists at dispatch time, skip (no mark)."""
    security = _make_security()
    alert = _make_alert(security_id=security.id)
    user = MagicMock()
    user.email = "trader@example.com"

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_by_id = AsyncMock(return_value=alert)

    security_repo = AsyncMock(spec=SecurityRepository)
    security_repo.get_by_id_or_fail = AsyncMock(return_value=security)

    user_repo = AsyncMock(spec=UserRepository)
    user_repo.get_by_id = AsyncMock(return_value=user)

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(return_value={})

    mc = _mock_container(
        alert_repo, security_repo, user_repo, AsyncMock(), intraday_repo
    )

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mc),
    ):
        await _alert_email_dispatch(alert.id, datetime.now(UTC))

    alert_repo.mark_triggered.assert_not_awaited()


# -- Exception propagation --


@pytest.mark.asyncio
async def test_stage3_send_exception_propagates_for_retry():
    """If email send raises, the exception propagates (for huey retry)."""
    security = _make_security()
    alert = _make_alert(security_id=security.id)
    user = MagicMock()
    user.email = "trader@example.com"

    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_by_id = AsyncMock(return_value=alert)

    security_repo = AsyncMock(spec=SecurityRepository)
    security_repo.get_by_id_or_fail = AsyncMock(return_value=security)

    user_repo = AsyncMock(spec=UserRepository)
    user_repo.get_by_id = AsyncMock(return_value=user)

    email_service = MagicMock(spec=EmailService)
    smtp_error = RuntimeError("SMTP down")
    email_service.send_price_alert_email = MagicMock(side_effect=smtp_error)

    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
        return_value={security.id: Decimal("200.00")}
    )

    mc = _mock_container(
        alert_repo, security_repo, user_repo, email_service, intraday_repo
    )

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mc),
        patch(
            "src.market.task.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw)),
        ),
        pytest.raises(RuntimeError, match="SMTP down"),
    ):
        await _alert_email_dispatch(alert.id, datetime.now(UTC))

    # Alert must NOT be marked triggered
    alert_repo.mark_triggered.assert_not_awaited()


@pytest.mark.asyncio
async def test_stage3_no_registry_returns_early():
    """When huey.svcs_registry is None, the task returns without error."""
    with patch("src.market.task.huey.svcs_registry", None):
        await _alert_email_dispatch(1, datetime.now(UTC))
    # Should not raise
