"""Alert evaluation and dispatch service for price alerts.

Owns the pure alert-condition evaluation logic and the Stage-3 email
dispatch orchestration, extracted out of Huey task bodies (ARCH-T03).
"""

import logging
from datetime import datetime
from decimal import Decimal

from svcs import Container

from src.auth.api import UserApi
from src.core.email import EmailService, PriceAlertEmailData
from src.market.api_types import SecurityId
from src.market.repository import (
    IntradayPriceRepository,
    PriceAlertRepository,
    SecurityRepository,
)
from src.market.schema import AlertForEvaluation

logger = logging.getLogger(__name__)


class AlertEvaluationService:
    """Service owning price-alert evaluation and email dispatch logic.

    Dependencies resolved via constructor — registered in svcs container
    for both prod and stub paths.
    """

    def __init__(
        self,
        alert_repo: PriceAlertRepository,
        security_repo: SecurityRepository,
        intraday_repo: IntradayPriceRepository,
        user_api: UserApi,
        email_service: EmailService,
    ) -> None:
        self._alert_repo = alert_repo
        self._security_repo = security_repo
        self._intraday_repo = intraday_repo
        self._user_api = user_api
        self._email_service = email_service

    # ------------------------------------------------------------------ #
    #  Pure evaluation logic — trivially unit-testable without Huey.
    # ------------------------------------------------------------------ #

    @staticmethod
    def evaluate(
        alerts: list[AlertForEvaluation],
        latest_prices: dict[SecurityId, Decimal],
    ) -> list[AlertForEvaluation]:
        """Evaluate alert conditions against latest intraday prices.

        Conditions are INCLUSIVE:
        - ``condition == "above"``  → trigger when ``latest >= target``
        - ``condition == "below"``  → trigger when ``latest <= target``

        Missing price for a security → alert skipped.

        Args:
            alerts: active alerts (triggered_at IS NULL) joined with security info.
            latest_prices: mapping of security_id → latest intraday close price.

        Returns:
            List of alerts whose condition was met.
        """
        triggered: list[AlertForEvaluation] = []
        for alert in alerts:
            latest_price = latest_prices.get(alert.security_id)
            if latest_price is None:
                logger.info(
                    "No intraday price for security %s (alert %d), skipping.",
                    alert.security_symbol,
                    alert.alert_id,
                )
                continue

            above_triggered = (
                alert.condition == "above" and latest_price >= alert.target_price
            )
            below_triggered = (
                alert.condition == "below" and latest_price <= alert.target_price
            )

            if above_triggered or below_triggered:
                logger.info(
                    "Alert %d triggered: %s %s (latest: %s, target: %s)",
                    alert.alert_id,
                    alert.condition,
                    alert.security_symbol,
                    latest_price,
                    alert.target_price,
                )
                triggered.append(alert)
        return triggered

    # ------------------------------------------------------------------ #
    #  Stage-3 dispatch: fetch security/user/price → send → mark_triggered.
    # ------------------------------------------------------------------ #

    async def dispatch_alert_email(self, alert_id: int, run_ts: datetime) -> None:
        """Send email for a triggered price alert, then mark as triggered.

        Email-then-mark pattern: send email first, only mark_triggered on
        success. Failed dispatch leaves ``triggered_at IS NULL`` so Stage 2
        re-enqueues next hour. On send error, re-raises so Huey retries.

        Args:
            alert_id: primary key of the triggered alert.
            run_ts: the evaluation run timestamp (threaded from Stage 2).
        """
        # Fresh fetch — idempotency guard against duplicate dispatch from retry
        alert = await self._alert_repo.get_by_id(alert_id)
        if alert is None or alert.triggered_at is not None:
            logger.info("Alert %d inactive/already-triggered; no-op", alert_id)
            return

        # Fetch security for name/symbol
        try:
            security = await self._security_repo.get_by_id_or_fail(alert.security_id)
        except Exception:
            logger.exception(
                "Security %s not found for alert %d, skipping email.",
                alert.security_id,
                alert_id,
            )
            return

        # Re-resolve latest price at dispatch time (not stale snapshot from Stage 2)
        latest_map = await self._intraday_repo.get_latest_intraday_close_by_security()
        latest_price = latest_map.get(alert.security_id)
        if latest_price is None:
            logger.info(
                "No intraday price for security %s at dispatch; skipping alert %d",
                security.symbol,
                alert_id,
            )
            return

        # Resolve user email via auth API facade
        email = await self._user_api.get_email_for_user(alert.user_id)
        if email is None:
            logger.warning(
                "User %s not found for alert %d, skipping email.",
                alert.user_id,
                alert_id,
            )
            return

        # Email-then-mark: send FIRST, only mark on success.
        try:
            alert_data = PriceAlertEmailData(
                security_id=alert.security_id,
                security_symbol=security.symbol,
                security_name=security.name,
                condition=alert.condition,
                target_price=alert.target_price,
                latest_price=latest_price,
            )
            await self._email_service.send_price_alert_email(
                recipient=email,
                alert=alert_data,
            )
        except Exception:
            logger.exception(
                "Failed to send price alert email for alert %d (user %s).",
                alert_id,
                alert.user_id,
            )
            raise  # re-raise so huey retries (retries=3); do NOT mark_triggered

        # Only mark triggered after successful send — exception propagates for retry
        await self._alert_repo.mark_triggered(alert_id, run_ts)
        logger.info(
            "Price alert email sent and marked triggered for alert %d.", alert_id
        )


async def alert_evaluation_service_factory(
    container: Container,
) -> AlertEvaluationService:
    """Factory for AlertEvaluationService (used by svcs registration)."""
    return AlertEvaluationService(
        alert_repo=await container.aget(PriceAlertRepository),
        security_repo=await container.aget(SecurityRepository),
        intraday_repo=await container.aget(IntradayPriceRepository),
        user_api=await container.aget(UserApi),
        email_service=await container.aget(EmailService),
    )
