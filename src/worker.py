from huey import MemoryHuey, RedisHuey
from huey_dashboard import init_worker_signals
from sqlalchemy.pool import NullPool
from svcs import Registry

from src.config.settings import settings


class HueyWithRegistry:
    svcs_registry: Registry | None = None


class RedisHueyWithRegistry(RedisHuey, HueyWithRegistry):
    pass


class MemoryHueyWithRegistry(MemoryHuey, HueyWithRegistry):
    pass


if settings.environment == "test":
    huey = MemoryHueyWithRegistry("retail-portfolio")
else:
    huey = RedisHueyWithRegistry("retail-portfolio", url=settings.redis_url)


@huey.on_startup()
def setup_worker_services():
    from src.config.database import DatabaseSessionManager  # noqa: PLC0415
    from src.config.logging import init_logging  # noqa: PLC0415
    from src.config.services import register_services  # noqa: PLC0415
    from src.observability import (  # noqa: PLC0415
        bootstrap_observability,
        get_tracer,
    )

    init_logging()
    bootstrap_observability(service_name="worker")
    tracer = get_tracer("src.worker")
    with tracer.start_as_current_span("worker.startup") as span:
        span.set_attribute("startup.status", "ok")

    init_worker_signals(
        huey=huey,  # ty: ignore[invalid-argument-type]
        db_url=settings.database_url,
        redis_url=settings.redis_url,
    )

    # Use NullPool for the worker to avoid "operation in progress" errors
    # during asyncio.run() task cycles.
    worker_sessionmanager = DatabaseSessionManager(
        str(settings.database_url),
        {"echo": settings.echo_sql, "poolclass": NullPool},
    )

    import src.config.database  # noqa: PLC0415

    src.config.database.sessionmanager = worker_sessionmanager

    registry = Registry()
    register_services(registry, worker_sessionmanager)
    huey.svcs_registry = registry

    if settings.environment != "test" and settings.enable_metrics:
        import prometheus_client  # noqa: PLC0415

        from src.core.metrics import (  # noqa: PLC0415
            REGISTRY,
            start_worker_metrics_updater,
        )

        prometheus_client.start_http_server(
            port=settings.worker_metrics_port,
            addr="0.0.0.0",  # noqa: S104
            registry=REGISTRY,
        )
        start_worker_metrics_updater(
            sessionmanager=worker_sessionmanager,
            huey_instance=huey,
        )


@huey.on_shutdown()
def teardown_worker_services():
    from src.observability import shutdown_observability  # noqa: PLC0415

    if huey.svcs_registry is not None:
        huey.svcs_registry.close()
    shutdown_observability()


# Import tasks to ensure they are registered with Huey
import src.account.task  # noqa: E402
import src.integration.task  # noqa: E402
import src.market.task  # noqa: E402
