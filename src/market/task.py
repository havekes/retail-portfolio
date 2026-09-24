import asyncio
import logging
from datetime import UTC, datetime

from huey import crontab
from huey_dashboard import TaskDatabase
from huey_dashboard.models.task import TaskInfo
from svcs import Container

from src.account.task import recalculate_all_account_totals_task
from src.auth.api_types import UserId
from src.core.context import get_request_id, request_id_ctx_var, set_request_id
from src.market.ai_service import AIService
from src.market.alert_service import AlertEvaluationService
from src.market.api_types import SecurityId
from src.market.repository import (
    IntradayPriceRepository,
    PriceAlertRepository,
    SecurityNoteRepository,
    SecurityNoteSummaryRepository,
)
from src.market.schema import NoteSummaryWrite
from src.market.service import MarketService
from src.worker import huey

logger = logging.getLogger(__name__)


async def mark_task_cancelled(
    db: TaskDatabase, task_id: str, task_name: str, reason: str
) -> None:
    """Write a ``cancelled`` row for a revoked huey task; never raises.

    The worker keeps a task row ``executing`` when its checkpoint guard
    abandons an in-flight run (there is no in-body accessor for the huey task
    id in huey 3.4.0). The visible *cancelled* state therefore comes from the
    backend at revoke time, using the dashboard database already on
    ``app.state.huey_dashboard``.
    """
    try:
        await db.upsert_task(
            TaskInfo(
                id=task_id,
                name=task_name,
                status="cancelled",
                error=reason,
                timestamp=datetime.now(UTC),
            )
        )
    except Exception:
        logger.warning("Failed to mark task %s as cancelled", task_id, exc_info=True)


@huey.task()
def generate_note_title_task(note_id: int, request_id: str | None = None) -> None:
    """Huey task to generate a note's title and one-sentence summary using AI."""
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
                logger.info(
                    "Discarding title generation for note %d — note deleted", note_id
                )
                return

            title, summary = await ai_service.generate_note_title_and_summary(
                note.content
            )

            # The note may have been deleted while the AI call was in flight;
            # discarding the result keeps the deleted row untouched.
            note = await note_repository.get_by_id(note_id)
            if not note:
                logger.info(
                    "Discarding title generation for note %d — note deleted", note_id
                )
                return

            await note_repository.update_title_and_summary(note_id, title, summary)
            logger.info("Generated title for note %d: %s", note_id, title)
            if summary:
                logger.info("Generated summary for note %d", note_id)
    finally:
        if req_token is not None:
            request_id_ctx_var.reset(req_token)


@huey.task()
def generate_note_summary_task(
    security_id: SecurityId, user_id: UserId, request_id: str | None = None
) -> None:
    """Huey task to regenerate the persisted note summary using AI."""
    if request_id is None:
        request_id = get_request_id()

    asyncio.run(_generate_note_summary(security_id, user_id, request_id=request_id))


async def _generate_note_summary(
    security_id: SecurityId, user_id: UserId, request_id: str | None = None
) -> None:
    """Regenerate the stored note summary for (security, user).

    With no notes left the stored summary is cleared instead of calling the
    AI. Any failure (AI error, timeout) is logged and swallowed: the previously
    stored summary stays untouched and the worker never crashes.
    """
    if huey.svcs_registry is None:
        return

    req_token = set_request_id(request_id) if request_id else None

    try:
        async with Container(huey.svcs_registry) as svcs_container:
            note_repository: SecurityNoteRepository = await svcs_container.aget(
                SecurityNoteRepository
            )
            ai_service: AIService = await svcs_container.aget(AIService)
            summary_repository: SecurityNoteSummaryRepository = (
                await svcs_container.aget(SecurityNoteSummaryRepository)
            )

            try:
                notes, _ = await note_repository.get_by_security_and_user(
                    security_id, user_id, limit=1
                )
                if not notes:
                    await summary_repository.delete(security_id, user_id)
                    logger.info(
                        "Cleared note summary for security %s, user %s (no notes left)",
                        security_id,
                        user_id,
                    )
                    return

                summary = await ai_service.summarize_notes(security_id, user_id)

                # Notes may have been deleted while the AI call was in flight;
                # discard the result and clear the stored summary instead of
                # persisting a summary for a now-empty note set.
                notes, _ = await note_repository.get_by_security_and_user(
                    security_id, user_id, limit=1
                )
                if not notes:
                    await summary_repository.delete(security_id, user_id)
                    logger.info(
                        "Discarded note summary for security %s, user %s and "
                        "cleared stored summary — notes deleted during generation",
                        security_id,
                        user_id,
                    )
                    return

                # A thought-only response (or an unparseable one) cleans down to
                # two empty parts. Upserting them would wipe a previously good
                # summary, so keep the stored row and let the next regeneration
                # try again.
                if (
                    not summary["short_summary"].strip()
                    and not summary["long_summary"].strip()
                ):
                    logger.warning(
                        "Empty summary parts for security %s, user %s — "
                        "keeping previous summary",
                        security_id,
                        user_id,
                    )
                    return

                await summary_repository.upsert(
                    NoteSummaryWrite(
                        short_summary=summary["short_summary"],
                        long_summary=summary["long_summary"],
                        generated_at=datetime.now(UTC),
                    ),
                    security_id,
                    user_id,
                )
                logger.info(
                    "Generated note summary for security %s, user %s",
                    security_id,
                    user_id,
                )
            except Exception:
                logger.exception(
                    "Failed to generate note summary for security %s, user %s",
                    security_id,
                    user_id,
                )
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

        # Enqueue account totals recalculation (isolated — failure doesn't abort)
        if huey.svcs_registry is not None:
            try:
                recalculate_all_account_totals_task()
            except Exception:
                logger.exception(
                    "Failed to enqueue recalculate_all_account_totals_task"
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
    Delegates evaluation to AlertEvaluationService.
    """
    asyncio.run(_check_and_dispatch_price_alerts())


async def _check_and_dispatch_price_alerts() -> None:
    if huey.svcs_registry is None:
        return

    run_ts = datetime.now(UTC)

    async with Container(huey.svcs_registry) as svcs_container:
        alert_service: AlertEvaluationService = await svcs_container.aget(
            AlertEvaluationService
        )
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

        # Delegate evaluation to the service
        triggered_alerts = alert_service.evaluate(active_alerts, latest_prices)

        triggered_count = len(triggered_alerts)
        enqueued_count = 0
        for alert in triggered_alerts:
            try:
                # Enqueue Stage 3 email dispatch
                alert_email_dispatch_task(alert.alert_id, run_ts)
                enqueued_count += 1
            except Exception:
                logger.exception(
                    "Failed to enqueue alert email dispatch for alert %d",
                    alert.alert_id,
                )
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

    Delegates to AlertEvaluationService.dispatch_alert_email.
    retries=3: transient SMTP/DB failures are retried before giving up.
    """
    asyncio.run(_alert_email_dispatch(alert_id, run_ts))


async def _alert_email_dispatch(alert_id: int, run_ts: datetime) -> None:
    if huey.svcs_registry is None:
        return

    async with Container(huey.svcs_registry) as svcs_container:
        alert_service: AlertEvaluationService = await svcs_container.aget(
            AlertEvaluationService
        )
        await alert_service.dispatch_alert_email(alert_id, run_ts)
