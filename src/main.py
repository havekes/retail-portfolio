import logging
from typing import Annotated

import svcs
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svcs.fastapi import DepContainer

from src.config.auth import oauth2_scheme
from src.config.logging import init_logging
from src.config.services import register_services
from src.config.settings import settings
from src.routers import init_routers

logger = logging.getLogger(__name__)

init_logging()


@svcs.fastapi.lifespan
async def lifespan(_: FastAPI, registry: svcs.Registry):
    register_services(registry)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="retail-portfolio",
    version="0.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allow_origins.split(",")],
    allow_credentials=True,
    allow_methods=[origin.strip() for origin in settings.cors_allow_methods.split(",")],
    allow_headers=[origin.strip() for origin in settings.cors_allow_headers.split(",")],
)

init_routers(app)


@app.get("/api/ping")
async def ping(
    services: DepContainer, _: Annotated[str, Depends(oauth2_scheme)]
) -> dict[str, str]:
    """Server healthcheck"""
    logger.debug(settings)

    session = await services.aget(AsyncSession)

    response: dict[str, str] = {}
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
