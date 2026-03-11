from huey import RedisHuey
from sqlalchemy.pool import NullPool
from svcs import Container, Registry

from src.config.settings import settings


class HueyWithRegistry(RedisHuey):
    svcs_registry: Registry | None = None
    svcs_container: Container | None = None


huey = HueyWithRegistry("retail-portfolio", url=settings.redis_url)


@huey.on_startup()
def setup_worker_services():
    from src.config.database import DatabaseSessionManager  # noqa: PLC0415
    from src.config.logging import init_logging  # noqa: PLC0415
    from src.config.services import register_services  # noqa: PLC0415

    init_logging()

    # Use NullPool for the worker to avoid "operation in progress" errors
    # during asyncio.run() task cycles.
    worker_sessionmanager = DatabaseSessionManager(
        str(settings.database_url),
        {"echo": settings.echo_sql, "poolclass": NullPool},
    )

    registry = Registry()
    register_services(registry, worker_sessionmanager)
    huey.svcs_registry = registry
    huey.svcs_container = Container(registry)


@huey.on_shutdown()
def teardown_worker_services():
    if huey.svcs_registry is not None:
        huey.svcs_registry.close()
    if huey.svcs_container is not None:
        huey.svcs_container.close()


# Import tasks to ensure they are registered with Huey
import src.integration.task  # noqa: E402
import src.market.task  # noqa: E402
