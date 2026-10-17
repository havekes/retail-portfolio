"""Prometheus metrics infrastructure gauges."""

import logging
import threading
import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Gauge,
    ProcessCollector,
    generate_latest,
)

logger = logging.getLogger(__name__)

REGISTRY = CollectorRegistry()
ProcessCollector(registry=REGISTRY)

QUEUE_DEPTH = Gauge(
    "queue_depth",
    "Number of pending Huey tasks",
    ["process"],
    registry=REGISTRY,
)
DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "Database connection pool size (-1 if NullPool/unavailable)",
    ["process"],
    registry=REGISTRY,
)
DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out",
    "Number of database connections currently checked out (-1 if NullPool/unavailable)",
    ["process"],
    registry=REGISTRY,
)
DB_POOL_CHECKED_IN = Gauge(
    "db_pool_checked_in",
    "Number of database connections currently checked in (-1 if NullPool/unavailable)",
    ["process"],
    registry=REGISTRY,
)
PROCESS_UPTIME_SECONDS = Gauge(
    "process_uptime_seconds",
    "Process uptime in seconds",
    ["process"],
    registry=REGISTRY,
)
REDIS_UP = Gauge(
    "redis_up",
    "Redis connectivity status (1=up, 0=down)",
    ["process"],
    registry=REGISTRY,
)
DB_UP = Gauge(
    "db_up",
    "Database pool connectivity status (1=up, 0=down)",
    ["process"],
    registry=REGISTRY,
)

_START_TIME: float = time.monotonic()
_INITIALIZED_PROCESSES: set[str] = set()


def _ensure_process_gauges(process: str) -> None:
    """Ensure all series exist with default values before the first scrape."""
    if process not in _INITIALIZED_PROCESSES:
        QUEUE_DEPTH.labels(process=process).set(0)
        DB_POOL_SIZE.labels(process=process).set(-1)
        DB_POOL_CHECKED_OUT.labels(process=process).set(-1)
        DB_POOL_CHECKED_IN.labels(process=process).set(-1)
        REDIS_UP.labels(process=process).set(0)
        DB_UP.labels(process=process).set(0)
        _INITIALIZED_PROCESSES.add(process)


def _read_queue_depth(huey_instance: Any = None) -> int:
    if huey_instance is None:
        from src.worker import huey as default_huey  # noqa: PLC0415

        huey_instance = default_huey

    if hasattr(huey_instance, "pending") and callable(huey_instance.pending):
        pending = huey_instance.pending()
        return len(pending)
    if hasattr(huey_instance, "storage") and hasattr(huey_instance.storage, "pending"):
        return len(huey_instance.storage.pending())
    msg = "Huey instance has no supported pending() method"
    raise RuntimeError(msg)


def _read_db_pool(sessionmanager: Any = None) -> tuple[int, int, int]:
    if sessionmanager is None:
        from src.config.database import sessionmanager as default_sm  # noqa: PLC0415

        sessionmanager = default_sm

    if sessionmanager is None or getattr(sessionmanager, "engine", None) is None:
        return -1, -1, -1

    pool = getattr(sessionmanager.engine, "pool", None)
    if pool is None:
        return -1, -1, -1

    size = pool.size() if hasattr(pool, "size") and callable(pool.size) else -1
    checked_out = (
        pool.checkedout()
        if hasattr(pool, "checkedout") and callable(pool.checkedout)
        else -1
    )
    checked_in = (
        pool.checkedin()
        if hasattr(pool, "checkedin") and callable(pool.checkedin)
        else -1
    )
    return size, checked_out, checked_in


def update_infra_gauges(
    process: str = "backend",
    sessionmanager: Any = None,
    huey_instance: Any = None,
) -> None:
    """Update infrastructure gauges with current values, handling degradation."""
    _ensure_process_gauges(process)
    PROCESS_UPTIME_SECONDS.labels(process=process).set(time.monotonic() - _START_TIME)

    try:
        depth = _read_queue_depth(huey_instance)
        QUEUE_DEPTH.labels(process=process).set(depth)
        REDIS_UP.labels(process=process).set(1)
    except Exception:
        logger.warning(
            "Failed to read queue depth for process %s; leaving gauge stale/zeroed",
            process,
            exc_info=True,
        )
        REDIS_UP.labels(process=process).set(0)

    try:
        size, checked_out, checked_in = _read_db_pool(sessionmanager)
        DB_POOL_SIZE.labels(process=process).set(size)
        DB_POOL_CHECKED_OUT.labels(process=process).set(checked_out)
        DB_POOL_CHECKED_IN.labels(process=process).set(checked_in)
        DB_UP.labels(process=process).set(1)
    except Exception:
        logger.warning(
            "Failed to read DB pool metrics for process %s; leaving gauge stale/empty",
            process,
            exc_info=True,
        )
        DB_UP.labels(process=process).set(0)


def metrics_response() -> str:
    """Return latest metrics formatted in Prometheus text format."""
    return generate_latest(REGISTRY).decode("utf-8")


def start_worker_metrics_updater(
    interval_seconds: float = 15.0,
    sessionmanager: Any = None,
    huey_instance: Any = None,
) -> threading.Timer:
    """Start background timer loop calling update_infra_gauges for the worker."""

    def _tick() -> None:
        try:
            update_infra_gauges(
                process="worker",
                sessionmanager=sessionmanager,
                huey_instance=huey_instance,
            )
        except Exception:
            logger.warning("Failed updating worker infra gauges", exc_info=True)
        timer = threading.Timer(interval_seconds, _tick)
        timer.daemon = True
        timer.start()

    update_infra_gauges(
        process="worker",
        sessionmanager=sessionmanager,
        huey_instance=huey_instance,
    )
    timer = threading.Timer(interval_seconds, _tick)
    timer.daemon = True
    timer.start()
    return timer


router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint() -> PlainTextResponse:
    """Prometheus metrics endpoint."""
    update_infra_gauges(process="backend")
    return PlainTextResponse(metrics_response(), media_type=CONTENT_TYPE_LATEST)
