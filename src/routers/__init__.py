from fastapi import FastAPI

from src.routers.accounts import router as account_router
from src.routers.auth import router as auth_router
from src.routers.external import router as external_router
from src.routers.positions import router as positions_router


def init_routers(app: FastAPI) -> None:
    app.include_router(external_router)
    app.include_router(account_router)
    app.include_router(positions_router)
    app.include_router(auth_router)
