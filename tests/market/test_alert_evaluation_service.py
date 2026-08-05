# ruff: noqa: PLR0913, PLR2004
"""Tests for AlertEvaluationService — pure eval logic and dispatch orchestration."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.auth.api import UserApi
from src.core.email import EmailService, PriceAlertEmailData
from src.market.alert_service import AlertEvaluationService
from src.market.repository import (
    IntradayPriceRepository,
    PriceAlertRepository,
    SecurityRepository,
)
from src.market.schema import AlertForEvaluation, PriceAlertRead, SecuritySchema

# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #


def _make_alert(
    *,
    alert_id: int = 1,
    security_id=None,
    security_symbol: str = "AAPL",
    security_name: str = "Apple Inc.",
    target_price: Decimal = Decimal("150.00"),
    condition: str = "above",
) -> AlertForEvaluation:
    return AlertForEvaluation(
        alert_id=alert_id,
        security_id=security_id or uuid4(),
        security_symbol=security_symbol,
        security_name=security_name,
        user_id=uuid4(),
        target_price=target_price,
        condition=condition,
    )


def _make_security(
    *,
    symbol: str = "AAPL",
    name: str = "Apple Inc.",
) -> SecuritySchema:
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


def _make_db_alert(
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


def _make_service(
    alert_repo=None,
    security_repo=None,
    intraday_repo=None,
    user_api=None,
    email_service=None,
) -> AlertEvaluationService:
    return AlertEvaluationService(
        alert_repo=alert_repo or AsyncMock(spec=PriceAlertRepository),
        security_repo=security_repo or AsyncMock(spec=SecurityRepository),
        intraday_repo=intraday_repo or AsyncMock(spec=IntradayPriceRepository),
        user_api=user_api or AsyncMock(spec=UserApi),
        email_service=email_service or AsyncMock(spec=EmailService),
    )


# --------------------------------------------------------------------------- #
#  evaluate() — pure logic, no Huey needed
# --------------------------------------------------------------------------- #


class TestEvaluate:
    """Pure evaluation logic tests."""

    def test_no_alerts_returns_empty(self):
        assert AlertEvaluationService.evaluate([], {}) == []

    def test_above_triggered(self):
        sec_id = uuid4()
        alert = _make_alert(
            security_id=sec_id,
            target_price=Decimal("150.00"),
            condition="above",
        )
        latest_prices = {sec_id: Decimal("155.00")}
        triggered = AlertEvaluationService.evaluate([alert], latest_prices)
        assert len(triggered) == 1
        assert triggered[0].alert_id == alert.alert_id

    def test_below_triggered(self):
        sec_id = uuid4()
        alert = _make_alert(
            security_id=sec_id,
            target_price=Decimal("150.00"),
            condition="below",
        )
        latest_prices = {sec_id: Decimal("145.00")}
        triggered = AlertEvaluationService.evaluate([alert], latest_prices)
        assert len(triggered) == 1

    def test_boundary_inclusive_above(self):
        """Price exactly at target triggers 'above' (inclusive boundary)."""
        sec_id = uuid4()
        alert = _make_alert(
            security_id=sec_id,
            target_price=Decimal("150.00"),
            condition="above",
        )
        latest_prices = {sec_id: Decimal("150.00")}
        triggered = AlertEvaluationService.evaluate([alert], latest_prices)
        assert len(triggered) == 1

    def test_boundary_inclusive_below(self):
        """Price exactly at target triggers 'below' (inclusive boundary)."""
        sec_id = uuid4()
        alert = _make_alert(
            security_id=sec_id,
            target_price=Decimal("150.00"),
            condition="below",
        )
        latest_prices = {sec_id: Decimal("150.00")}
        triggered = AlertEvaluationService.evaluate([alert], latest_prices)
        assert len(triggered) == 1

    def test_not_triggered_price_not_reached(self):
        """Alert does NOT fire when price hasn't crossed the threshold."""
        sec_id = uuid4()
        alert = _make_alert(
            security_id=sec_id,
            target_price=Decimal("200.00"),
            condition="above",
        )
        latest_prices = {sec_id: Decimal("150.00")}
        triggered = AlertEvaluationService.evaluate([alert], latest_prices)
        assert len(triggered) == 0

    def test_no_price_for_security_skips(self):
        """Alert with no intraday price for its security is skipped."""
        sec_id = uuid4()
        alert = _make_alert(security_id=sec_id)
        triggered = AlertEvaluationService.evaluate([alert], {})
        assert len(triggered) == 0

    def test_multiple_alerts_mixed_results(self):
        """Some trigger, some don't — correct subset returned."""
        sec_id_1 = uuid4()
        sec_id_2 = uuid4()
        sec_id_3 = uuid4()
        alerts = [
            _make_alert(
                alert_id=1,
                security_id=sec_id_1,
                target_price=Decimal("150.00"),
                condition="above",
            ),
            _make_alert(
                alert_id=2,
                security_id=sec_id_2,
                target_price=Decimal("200.00"),
                condition="above",
            ),
            _make_alert(
                alert_id=3,
                security_id=sec_id_3,
                target_price=Decimal("150.00"),
                condition="below",
            ),
        ]
        latest_prices = {
            sec_id_1: Decimal("155.00"),  # triggers (above, 155 >= 150)
            sec_id_2: Decimal("180.00"),  # does NOT trigger (above, 180 < 200)
            sec_id_3: Decimal("140.00"),  # triggers (below, 140 <= 150)
        }
        triggered = AlertEvaluationService.evaluate(alerts, latest_prices)
        assert len(triggered) == 2
        assert {a.alert_id for a in triggered} == {1, 3}


# --------------------------------------------------------------------------- #
#  dispatch_alert_email() — with mocked deps
# --------------------------------------------------------------------------- #


class TestDispatchAlertEmail:
    """Dispatch orchestration tests with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_already_triggered_is_noop(self):
        """If alert.triggered_at is not None, dispatch is a no-op."""
        alert = _make_db_alert(triggered_at=datetime.now(UTC))
        alert_repo = AsyncMock(spec=PriceAlertRepository)
        alert_repo.get_by_id = AsyncMock(return_value=alert)

        svc = _make_service(alert_repo=alert_repo)
        await svc.dispatch_alert_email(alert.id, datetime.now(UTC))

        alert_repo.get_by_id.assert_awaited_once()
        alert_repo.mark_triggered.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_alert_not_found_is_noop(self):
        """If alert is None (deleted), dispatch is a no-op."""
        alert_repo = AsyncMock(spec=PriceAlertRepository)
        alert_repo.get_by_id = AsyncMock(return_value=None)

        svc = _make_service(alert_repo=alert_repo)
        await svc.dispatch_alert_email(999, datetime.now(UTC))

        alert_repo.mark_triggered.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sends_email_and_marks_triggered(self):
        """Full happy path: fetch alert → send email → mark triggered."""
        security = _make_security(symbol="TSLA", name="Tesla")
        user_id = uuid4()
        alert = _make_db_alert(
            security_id=security.id,
            user_id=user_id,
            target_price=Decimal("200.00"),
            condition="above",
        )
        user_api = AsyncMock(spec=UserApi)
        user_api.get_email_for_user = AsyncMock(return_value="trader@example.com")

        run_ts = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)
        latest_price = Decimal("205.00")

        alert_repo = AsyncMock(spec=PriceAlertRepository)
        alert_repo.get_by_id = AsyncMock(return_value=alert)

        security_repo = AsyncMock(spec=SecurityRepository)
        security_repo.get_by_id_or_fail = AsyncMock(return_value=security)

        email_service = AsyncMock(spec=EmailService)
        email_service.send_price_alert_email = AsyncMock()

        intraday_repo = AsyncMock(spec=IntradayPriceRepository)
        intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
            return_value={security.id: latest_price}
        )

        svc = _make_service(
            alert_repo=alert_repo,
            security_repo=security_repo,
            intraday_repo=intraday_repo,
            user_api=user_api,
            email_service=email_service,
        )
        await svc.dispatch_alert_email(alert.id, run_ts)

        # Email was sent with REAL latest price (not target_price)
        expected_alert = PriceAlertEmailData(
            security_id=alert.security_id,
            security_symbol=security.symbol,
            security_name=security.name,
            condition=alert.condition,
            target_price=alert.target_price,
            latest_price=latest_price,
        )
        email_service.send_price_alert_email.assert_called_once_with(
            recipient="trader@example.com",
            alert=expected_alert,
        )

        # Alert was marked triggered with the run_ts
        alert_repo.mark_triggered.assert_called_once_with(alert.id, run_ts)

    @pytest.mark.asyncio
    async def test_security_missing_skips(self):
        """If security lookup fails, dispatch is skipped (no mark_triggered)."""
        security_id = uuid4()
        alert = _make_db_alert(security_id=security_id)

        alert_repo = AsyncMock(spec=PriceAlertRepository)
        alert_repo.get_by_id = AsyncMock(return_value=alert)

        security_repo = AsyncMock(spec=SecurityRepository)
        security_repo.get_by_id_or_fail = AsyncMock(side_effect=Exception("not found"))

        svc = _make_service(alert_repo=alert_repo, security_repo=security_repo)
        await svc.dispatch_alert_email(alert.id, datetime.now(UTC))

        alert_repo.mark_triggered.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_user_missing_skips(self):
        """If user lookup returns None, dispatch is skipped."""
        security = _make_security()
        alert = _make_db_alert(security_id=security.id)

        alert_repo = AsyncMock(spec=PriceAlertRepository)
        alert_repo.get_by_id = AsyncMock(return_value=alert)

        security_repo = AsyncMock(spec=SecurityRepository)
        security_repo.get_by_id_or_fail = AsyncMock(return_value=security)

        user_api = AsyncMock(spec=UserApi)
        user_api.get_email_for_user = AsyncMock(return_value=None)

        intraday_repo = AsyncMock(spec=IntradayPriceRepository)
        intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
            return_value={security.id: Decimal("200.00")}
        )

        svc = _make_service(
            alert_repo=alert_repo,
            security_repo=security_repo,
            user_api=user_api,
            intraday_repo=intraday_repo,
        )
        await svc.dispatch_alert_email(alert.id, datetime.now(UTC))

        alert_repo.mark_triggered.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_intraday_price_at_dispatch_skips(self):
        """If no intraday price exists at dispatch time, skip (no mark)."""
        security = _make_security()
        alert = _make_db_alert(security_id=security.id)
        user_api = AsyncMock(spec=UserApi)
        user_api.get_email_for_user = AsyncMock(return_value="trader@example.com")

        alert_repo = AsyncMock(spec=PriceAlertRepository)
        alert_repo.get_by_id = AsyncMock(return_value=alert)

        security_repo = AsyncMock(spec=SecurityRepository)
        security_repo.get_by_id_or_fail = AsyncMock(return_value=security)

        intraday_repo = AsyncMock(spec=IntradayPriceRepository)
        intraday_repo.get_latest_intraday_close_by_security = AsyncMock(return_value={})

        svc = _make_service(
            alert_repo=alert_repo,
            security_repo=security_repo,
            user_api=user_api,
            intraday_repo=intraday_repo,
        )
        await svc.dispatch_alert_email(alert.id, datetime.now(UTC))

        alert_repo.mark_triggered.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_exception_propagates_for_retry(self):
        """If email send raises, the exception propagates (for huey retry)."""
        security = _make_security()
        alert = _make_db_alert(security_id=security.id)
        user_api = AsyncMock(spec=UserApi)
        user_api.get_email_for_user = AsyncMock(return_value="trader@example.com")

        alert_repo = AsyncMock(spec=PriceAlertRepository)
        alert_repo.get_by_id = AsyncMock(return_value=alert)

        security_repo = AsyncMock(spec=SecurityRepository)
        security_repo.get_by_id_or_fail = AsyncMock(return_value=security)

        email_service = AsyncMock(spec=EmailService)
        smtp_error = RuntimeError("SMTP down")
        email_service.send_price_alert_email = AsyncMock(side_effect=smtp_error)

        intraday_repo = AsyncMock(spec=IntradayPriceRepository)
        intraday_repo.get_latest_intraday_close_by_security = AsyncMock(
            return_value={security.id: Decimal("200.00")}
        )

        svc = _make_service(
            alert_repo=alert_repo,
            security_repo=security_repo,
            user_api=user_api,
            email_service=email_service,
            intraday_repo=intraday_repo,
        )

        with pytest.raises(RuntimeError, match="SMTP down"):
            await svc.dispatch_alert_email(alert.id, datetime.now(UTC))

        # Alert must NOT be marked triggered
        alert_repo.mark_triggered.assert_not_awaited()
