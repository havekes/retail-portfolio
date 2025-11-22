from asyncio import run

from src.database import sessionmanager
from src.models.user import User


async def main():
    async with sessionmanager.session() as session:
        email = input("User email: ")
        user = User(email=email, password="")
        session.add(user)
        await session.commit()


if __name__ == "__main__":
    run(main())
