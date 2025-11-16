from fastapi import FastAPI

import src.models  # noqa: F401  # Import models to ensure they are loaded
from src.routers.external import router

app = FastAPI()

app.include_router(router)


@app.get("/api/ping")
async def ping():
    """Check server status"""
    return {"ping": "pong"}
