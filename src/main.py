import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import redis
import svcs
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from huey_dashboard import init_huey_dashboard
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svcs.fastapi import DepContainer

from src.account.router import account_router, portfolio_router
from src.auth.router import auth_router
from src.config.database import sessionmanager
from src.config.logging import init_logging
from src.config.services import register_services
from src.config.settings import settings
from src.core.exception import AuthorizationError, EntityNotFoundError
from src.integration.router import institutions_router, integration_router
from src.market.router import market_router
from src.ws.manager import ws_manager
from src.ws.router import ws_router

from .worker import huey


@asynccontextmanager
async def lifespan_context(app: FastAPI):
    # Initialize services
    registry = svcs.Registry()
    app.state.svcs_registry = registry
    register_services(registry, sessionmanager)

    # Initialize WebSocket manager
    await ws_manager.init_redis(settings.redis_url)

    # Initialize Huey dashboard
    init_huey_dashboard(
        app,
        huey=huey,  # ty: ignore[invalid-argument-type]
        db_url=settings.database_url,
        redis_url=settings.redis_url,
        api_prefix="/worker/api",
        bind_signals=True,
    )

    try:
        async with registry:
            yield {"svcs_registry": registry}
    except Exception:
        logger.exception("Lifespan yield failed:")

    await ws_manager.close()


logger = logging.getLogger(__name__)

if settings.environment == "dev":
    import debugpy  # noqa: T100

    # Bind to all interfaces on 5678
    debugpy.listen(("0.0.0.0", 5678))  # noqa: S104, T100
    logger.info("⏳ Waiting for debugger to attach...")

app = FastAPI(
    lifespan=lifespan_context,
    title="retail-portfolio",
    version="0.0.0",
    debug=settings.environment != "prod",
)


@app.middleware("http")
async def cors_exception_middleware(request: Request, call_next: Any) -> Any:
    """
    Middleware to ensure CORS headers are present even on unhandled 500 errors.
    This acts as a safety net for exceptions that escape the normal FastAPI handlers.
    """
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled exception in middleware safety net:")

        allowed_origins = [
            origin.strip() for origin in settings.cors_allow_origins.split(",")
        ]
        origin = request.headers.get("origin")

        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal Server Error",
                "error": str(exc)
                if settings.environment != "prod"
                else "Internal Error",
            },
        )

        # Manually inject CORS headers if the origin is allowed
        if origin and (origin in allowed_origins or "*" in allowed_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        elif "*" in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"

        return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allow_origins.split(",")],
    allow_origin_regex=r"https?://.*" if settings.environment != "prod" else None,
    allow_credentials=True,
    allow_methods=[origin.strip() for origin in settings.cors_allow_methods.split(",")],
    allow_headers=[origin.strip() for origin in settings.cors_allow_headers.split(",")],
)

init_logging()
app.include_router(account_router)
app.include_router(portfolio_router)
app.include_router(auth_router)
app.include_router(institutions_router)
app.include_router(integration_router)
app.include_router(market_router)
app.include_router(ws_router)


@app.get("/api/ping")
async def ping(services: DepContainer) -> dict[str, Any]:
    """Server healthcheck"""
    session = await services.aget(AsyncSession)

    response: dict[str, Any] = {}
    response["ping"] = "pong"
    try:
        if (await session.execute(select(1))).scalar() == 1:
            response["database"] = "ok"
        else:
            response["database"] = "error"
    except Exception:
        logger.exception("Ping DB check failed")
        response["database"] = "error"

    return response


@app.exception_handler(Exception)
async def catch_all_exception_handler(_: Request, exc: Exception):
    # Use a safer logging call to avoid potential formatting errors
    logger.exception("Unhandled exception caught by FastAPI handler:")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "error": str(exc) if settings.environment != "prod" else "Internal Error",
        },
    )


@app.exception_handler(EntityNotFoundError)
async def entity_not_found_error_handler(_, error: EntityNotFoundError):
    if settings.environment != "prod":
        logger.exception(str(error))
    return JSONResponse(status_code=404, content={"error": str(error)})


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(_, error: AuthorizationError):
    if settings.environment != "prod":
        logger.exception(error.log_message())
    return JSONResponse(status_code=404, content={"error": str(error)})
