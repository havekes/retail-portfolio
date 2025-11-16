from fastapi import FastAPI

from src.routers.external import router

app = FastAPI()

app.include_router(router)


@app.get("/api/ping")
async def ping():
    """Check server status"""
    return {"ping": "pong"}
