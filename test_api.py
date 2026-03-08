import asyncio
from httpx import AsyncClient
from src.main import app
from src.auth.service import create_access_token

async def test():
    token = create_access_token({'sub': '0e9181fa-e14b-4ac3-a17d-a30d998ca103'})
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/accounts/", headers={"Authorization": f"Bearer {token}"})
        print(response.json())

asyncio.run(test())
