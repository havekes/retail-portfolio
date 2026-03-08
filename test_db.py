import asyncio
from src.config.database import get_db, SessionLocal
from sqlalchemy import select
from src.account.model import AccountModel

async def test():
    async with SessionLocal() as session:
        result = await session.execute(select(AccountModel).limit(1))
        account = result.scalar_one()
        print(f"Account UUID: {account.id}, Broker Display Name: {account.broker_display_name}")

asyncio.run(test())
