import asyncio
import logging
from datetime import UTC, datetime

from huey import crontab
from svcs import Container

from src.account.service.account import AccountService
from src.account.service.position import PositionService
from src.auth.repository import UserRepository
from src.core.context import get_request_id, request_id_ctx_var, set_request_id
from src.core.email import EmailService, PriceAlertEmailData
from src.market.ai_service import AIService
from src.market.repository import (
    IntradayPriceRepository,
    PriceAlertRepository,
    SecurityNoteRepository,
    SecurityRepository,
)
from src.market.service import MarketService
from src.worker import huey
from src.ws.api_types import AccountTotalsUpdatedMessage
from src.ws.manager import ws_manager

logger = logging.getLogger(__name__)


@huey.task()
def generate_note_title_task(note_id: int, request_id: str | None = None) -> None:
    """Huey task to generate note title using AI."""
    if request_id is None:
        request_id = get_request_id()

    asyncio.run(_generate_note_title(note_id, request_id=request_id))


async def _generate_note_title(note_id: int, request_id: str | None = None) -> None:
    if huey.svcs_registry is None:
        return

    req_token = set_request_id(request_id) if request_id else None

    try:
        async with Container(huey.svcs_registry) as svcs_container:
            note_repository: SecurityNoteRepository = await svcs_container.aget(
                SecurityNoteRepository
            )
            ai_service: AIService = await svcs_container.aget(AIService)

            note = await note_repository.get_by_id(note_id)
            if not note:
                logger.warning("Note %d not found for title generation", note_id)
                return

            title = await ai_service.generate_note_title(note.content)
            await note_repository.update_title(note_id, title)
            logger.info("Generated title for note %d: %s", note_id, title)
    finally:
        if req_token is not None:
            request_id_ctx_var.reset(req_token)


@huey.periodic_task(crontab(hour="0", minute="0"))
def daily_price_update() -> None:
    """Huey periodic task to run daily price updates at midnight.

    Runs in the huey-worker process via thread workers.
    Uses asyncio.run() to execute the async business logic.
    """
    asyncio.run(_daily_price_update())


async def _daily_price_update() -> None:
    if huey.svcs_registry is None:
        msg = "Worker registry not initialized"
        raise RuntimeError(msg)

    async with Container(huey.svcs_registry) as svcs_container:
        market_service: MarketService = await svcs_container.aget(MarketService)

        logger.info("Starting daily price update for all active securities...")
        result = await market_service.update_daily_prices_for_all_securities()

        success = result.get("success", 0)
        failure = result.get("failure", 0)

        logger.info(
            "Daily price update completed. Successfully updated: %s | Failed: %s",
            success,
            failure,
        )


@huey.periodic_task(crontab(minute="0"))
def hourly_intraday_price_update() -> None:
    """Huey periodic task to run hourly intraday price updates.

    Runs in the huey-worker process via thread workers.
    Uses asyncio.run() to execute the async business logic.
    """
    asyncio.run(_hourly_intraday_price_update())


async def _hourly_intraday_price_update() -> None:
    if huey.svcs_registry is None:
        msg = "Worker registry not initialized"
        raise RuntimeError(msg)

    async with Container(huey.svcs_registry) as svcs_container:
        market_service: MarketService = await svcs_container.aget(MarketService)

        logger.info(
            "Starting hourly intraday price update for all active securities..."
        )
        result = await market_service.update_intraday_prices_for_all_securities()

        success = result.get("success", 0)
        failure = result.get("failure", 0)

        logger.info(
            "Hourly intraday price update completed. Successfully updated: %s | "
            "Failed: %s",
            success,
            failure,
        )

        account_service: AccountService = await svcs_container.aget(AccountService)
        position_service: PositionService = await svcs_container.aget(PositionService)

        accounts = await account_service.get_all_accounts()
        for account in accounts:
            if not account.is_active:
                continue
            try:
                totals = await position_service.get_total_for_account(
                    account.id, account.currency
                )
                msg = AccountTotalsUpdatedMessage(
                    account_id=account.id,
                    totals=totals,
                )
                await ws_manager.send_personal_message(
                    msg.model_dump(mode="json"), account.user_id
                )
            except Exception:
                logger.exception(
                    "Failed to update totals and send WS message for account %s",
                    account.id,
                )

        # Enqueue Stage 2: price alert evaluation (isolated — failure doesn't abort)
        if huey.svcs_registry is not None:
            try:
                check_and_dispatch_price_alerts()
            except Exception:
                logger.exception("Failed to enqueue check_and_dispatch_price_alerts")


@huey.task()
def check_and_dispatch_price_alerts() -> None:
    """Stage 2: Evaluate all active price alerts and dispatch emails for triggered ones.

    Called at the end of the hourly intraday price update (Stage 1).
    Uses split-query approach: fetch all active alerts and all latest prices
    separately, then map in memory.
    """
    asyncio.run(_check_and_dispatch_price_alerts())


async def _check_and_dispatch_price_alerts() -> None:
    if huey.svcs_registry is None:
        return

    run_ts = datetime.now(UTC)

    async with Container(huey.svcs_registry) as svcs_container:
        alert_repo: PriceAlertRepository = await svcs_container.aget(
            PriceAlertRepository
        )
        intraday_repo: IntradayPriceRepository = await svcs_container.aget(
            IntradayPriceRepository
        )

        # Fetch all active (not yet triggered) alerts — joined with security info
        active_alerts = await alert_repo.get_active_alerts_for_evaluation()
        if not active_alerts:
            logger.info("No active price alerts to evaluate.")
            return

        logger.info("Evaluating %d active price alert(s).", len(active_alerts))

        # Fetch latest intraday close for all securities (single query)
        latest_prices = await intraday_repo.get_latest_intraday_close_by_security()

        triggered_count = 0
        enqueued_count = 0
        for alert in active_alerts:
            try:
                latest_price = latest_prices.get(alert.security_id)
                if latest_price is None:
                    logger.info(
                        "No intraday price for security %s (alert %d), skipping.",
                        alert.security_symbol,
                        alert.alert_id,
                    )
                    continue

                # Evaluate condition (inclusive boundary)
                above_triggered = (
                    alert.condition == "above" and latest_price >= alert.target_price
                )
                below_triggered = (
                    alert.condition == "below" and latest_price <= alert.target_price
                )
                triggered = above_triggered or below_triggered

                if triggered:
                    logger.info(
                        "Alert %d triggered: %s %s (latest: %s, target: %s)",
                        alert.alert_id,
                        alert.condition,
                        alert.security_symbol,
                        latest_price,
                        alert.target_price,
                    )
                    # Enqueue Stage 3 email dispatch
                    alert_email_dispatch_task(alert.alert_id, run_ts)
                    triggered_count += 1
                    enqueued_count += 1
            except Exception:
                logger.exception("Failed to evaluate/enqueue alert %d", alert.alert_id)
                continue

        logger.info(
            "Price alert evaluation complete. evaluated=%d triggered=%d enqueued=%d",
            len(active_alerts),
            triggered_count,
            enqueued_count,
        )


@huey.task(retries=3)
def alert_email_dispatch_task(alert_id: int, run_ts: datetime) -> None:
    """Stage 3: Send email for a triggered price alert, then mark as triggered.

    Email-then-mark pattern: send email first, only mark_triggered on success.
    Failed dispatch leaves triggered_at IS NULL so Stage 2 re-enqueues next hour.
    retries=3: transient SMTP/DB failures are retried before giving up.
    """
    asyncio.run(_alert_email_dispatch(alert_id, run_ts))


async def _alert_email_dispatch(alert_id: int, run_ts: datetime) -> None:
    if huey.svcs_registry is None:
        return

    async with Container(huey.svcs_registry) as svcs_container:
        alert_repo: PriceAlertRepository = await svcs_container.aget(
            PriceAlertRepository
        )
        security_repo: SecurityRepository = await svcs_container.aget(
            SecurityRepository
        )
        user_repo: UserRepository = await svcs_container.aget(UserRepository)
        email_service: EmailService = await svcs_container.aget(EmailService)
        intraday_repo: IntradayPriceRepository = await svcs_container.aget(
            IntradayPriceRepository
        )

        # Fresh fetch — idempotency guard against duplicate dispatch from retry
        alert = await alert_repo.get_by_id(alert_id)
        if alert is None or alert.triggered_at is not None:
            logger.info("Alert %d inactive/already-triggered; no-op", alert_id)
            return

        # Fetch security for name/symbol
        try:
            security = await security_repo.get_by_id_or_fail(alert.security_id)
        except Exception:
            logger.exception(
                "Security %s not found for alert %d, skipping email.",
                alert.security_id,
                alert_id,
            )
            return

        # Re-resolve latest price at dispatch time (not stale snapshot from Stage 2)
        latest_map = await intraday_repo.get_latest_intraday_close_by_security()
        latest_price = latest_map.get(alert.security_id)
        if latest_price is None:
            logger.info(
                "No intraday price for security %s at dispatch; skipping alert %d",
                security.symbol,
                alert_id,
            )
            return

        # Resolve user email — user_id is a bare Uuid with NO FK to auth_users
        user = await user_repo.get_by_id(alert.user_id)
        if user is None:
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
            await email_service.send_price_alert_email(
                recipient=user.email,
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
        await alert_repo.mark_triggered(alert_id, run_ts)
        logger.info(
            "Price alert email sent and marked triggered for alert %d.", alert_id
        )
