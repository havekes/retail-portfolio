from huey import RedisHuey
from huey_dashboard import init_worker_signals
from sqlalchemy.pool import NullPool
from svcs import Registry

from src.config.settings import settings


class HueyWithRegistry(RedisHuey):
    svcs_registry: Registry | None = None


huey = HueyWithRegistry("retail-portfolio", url=settings.redis_url)


@huey.on_startup()
def setup_worker_services():
    from src.config.database import DatabaseSessionManager  # noqa: PLC0415
    from src.config.logging import init_logging  # noqa: PLC0415
    from src.config.services import register_services  # noqa: PLC0415

    init_logging()

    init_worker_signals(
        huey=huey,
        db_url=settings.database_url,
        redis_url=settings.redis_url,
    )

    # Use NullPool for the worker to avoid "operation in progress" errors
    # during asyncio.run() task cycles.
    worker_sessionmanager = DatabaseSessionManager(
        str(settings.database_url),
        {"echo": settings.echo_sql, "poolclass": NullPool},
    )

    registry = Registry()
    register_services(registry, worker_sessionmanager)
    huey.svcs_registry = registry


@huey.on_shutdown()
def teardown_worker_services():
    if huey.svcs_registry is not None:
        huey.svcs_registry.close()


# Import tasks to ensure they are registered with Huey
import src.integration.task  # noqa: E402
import src.market.task  # noqa: E402
