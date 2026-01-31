from asyncio import run

from src.auth.model import UserModel
from src.config.database import sessionmanager


async def main():
    async with sessionmanager.session() as session:
        email = input("User email: ")
        user = UserModel(email=email)
        session.add(user)
        await session.commit()


if __name__ == "__main__":
    run(main())
