import asyncio
import logging
import time
from datetime import UTC, datetime

from huey import crontab
from svcs import Container

from src.account.task import recalculate_all_account_totals_task
from src.core.context import get_request_id, request_id_ctx_var, set_request_id
from src.market.ai_service import AIService
from src.market.alert_service import AlertEvaluationService
from src.market.repository import (
    IntradayPriceRepository,
    PriceAlertRepository,
    SecurityNoteRepository,
)
from src.market.schema import AlertForEvaluation
from src.market.service import MarketService
from src.observability import capture_task_context, emit_event, restore_task_context
from src.worker import huey

logger = logging.getLogger(__name__)

#: Upper bound on the per-symbol outcomes carried by one ``alert.evaluated`` event.
_MAX_SYMBOL_OUTCOMES = 50


def _elapsed_ms(started: float) -> float:
    """Return milliseconds elapsed since a ``time.monotonic()`` reading."""
    return round((time.monotonic() - started) * 1000, 3)


def _symbol_outcomes(
    active_alerts: list[AlertForEvaluation],
    triggered_alerts: list[AlertForEvaluation],
) -> dict[str, str | bool]:
    """Build the bounded per-symbol outcome mapping for ``alert.evaluated``."""
    unique_symbols = list(
        dict.fromkeys(alert.security_symbol for alert in active_alerts)
    )
    triggered_symbols = {alert.security_symbol for alert in triggered_alerts}
    symbol_outcomes: dict[str, str | bool] = {
        symbol: "triggered" if symbol in triggered_symbols else "no_trigger"
        for symbol in unique_symbols[:_MAX_SYMBOL_OUTCOMES]
    }
    if len(unique_symbols) > _MAX_SYMBOL_OUTCOMES:
        symbol_outcomes["truncated"] = True
    return symbol_outcomes


@huey.task()
def generate_note_title_task(
    note_id: int,
    request_id: str | None = None,
    traceparent: str | None = None,
) -> None:
    """Huey task to generate note title using AI."""
    if request_id is None:
        request_id = get_request_id()

    with restore_task_context(
        "generate_note_title_task",
        request_id=request_id,
        traceparent=traceparent,
    ):
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
    Periodic tasks have no enqueuer, so they root their own trace.
    """
    with restore_task_context("daily_price_update"):
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
    Periodic tasks have no enqueuer, so they root their own trace.
    """
    with restore_task_context("hourly_intraday_price_update"):
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
                recalculate_all_account_totals_task(**capture_task_context())
            except Exception:
                logger.exception(
                    "Failed to enqueue recalculate_all_account_totals_task"
                )

        # Enqueue Stage 2: price alert evaluation (isolated — failure doesn't abort)
        if huey.svcs_registry is not None:
            try:
                check_and_dispatch_price_alerts(**capture_task_context())
            except Exception:
                logger.exception("Failed to enqueue check_and_dispatch_price_alerts")


@huey.task()
def check_and_dispatch_price_alerts(
    request_id: str | None = None,
    traceparent: str | None = None,
) -> None:
    """Stage 2: Evaluate all active price alerts and dispatch emails for triggered ones.

    Called at the end of the hourly intraday price update (Stage 1).
    Delegates evaluation to AlertEvaluationService.
    """
    with restore_task_context(
        "check_and_dispatch_price_alerts",
        request_id=request_id,
        traceparent=traceparent,
    ):
        asyncio.run(_check_and_dispatch_price_alerts())


async def _check_and_dispatch_price_alerts() -> None:
    if huey.svcs_registry is None:
        return

    started = time.monotonic()
    run_ts = datetime.now(UTC)
    run_at = run_ts.isoformat()

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
            emit_event(
                "alert.evaluated",
                alerts_evaluated=0,
                alerts_triggered=0,
                duration_ms=_elapsed_ms(started),
                run_at=run_at,
                outcome="success",
            )
            return

        logger.info("Evaluating %d active price alert(s).", len(active_alerts))

        triggered_alerts: list[AlertForEvaluation] = []
        triggered_count = 0
        enqueued_count = 0
        try:
            # Fetch latest intraday close for all securities (single query)
            latest_prices = await intraday_repo.get_latest_intraday_close_by_security()

            # Delegate evaluation to the service
            triggered_alerts = alert_service.evaluate(active_alerts, latest_prices)
            triggered_count = len(triggered_alerts)

            for alert in triggered_alerts:
                try:
                    # Enqueue Stage 3 email dispatch
                    alert_email_dispatch_task(
                        alert.alert_id, run_ts, **capture_task_context()
                    )
                    enqueued_count += 1
                except Exception:
                    logger.exception(
                        "Failed to enqueue alert email dispatch for alert %d",
                        alert.alert_id,
                    )
                    continue
        except Exception:
            emit_event(
                "alert.evaluated",
                alerts_evaluated=len(active_alerts),
                alerts_triggered=triggered_count,
                duration_ms=_elapsed_ms(started),
                run_at=run_at,
                outcome="failure",
                error_slug="alert_evaluation_failed",
            )
            raise

        emit_event(
            "alert.evaluated",
            alerts_evaluated=len(active_alerts),
            alerts_triggered=triggered_count,
            symbol_outcomes=_symbol_outcomes(active_alerts, triggered_alerts),
            duration_ms=_elapsed_ms(started),
            run_at=run_at,
            outcome="success",
        )

        logger.info(
            "Price alert evaluation complete. evaluated=%d triggered=%d enqueued=%d",
            len(active_alerts),
            triggered_count,
            enqueued_count,
        )


@huey.task(retries=3)
def alert_email_dispatch_task(
    alert_id: int,
    run_ts: datetime,
    request_id: str | None = None,
    traceparent: str | None = None,
) -> None:
    """Stage 3: Send email for a triggered price alert, then mark as triggered.

    Delegates to AlertEvaluationService.dispatch_alert_email.
    retries=3: transient SMTP/DB failures are retried before giving up.
    """
    with restore_task_context(
        "alert_email_dispatch_task",
        request_id=request_id,
        traceparent=traceparent,
    ):
        asyncio.run(_alert_email_dispatch(alert_id, run_ts))


async def _alert_email_dispatch(alert_id: int, run_ts: datetime) -> None:
    if huey.svcs_registry is None:
        return

    async with Container(huey.svcs_registry) as svcs_container:
        alert_service: AlertEvaluationService = await svcs_container.aget(
            AlertEvaluationService
        )
        await alert_service.dispatch_alert_email(alert_id, run_ts)
