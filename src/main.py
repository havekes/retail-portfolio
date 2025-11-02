"""
Backend
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/api/ping")
def ping():
    """Check server status"""
    return {"ping": "pong"}
