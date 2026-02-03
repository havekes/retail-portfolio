import uuid
from asyncio import run
from datetime import UTC, datetime
from getpass import getpass

from src.auth.model import UserModel
from src.auth.schema import UserSchema
from src.config.database import sessionmanager


async def main():
    async with sessionmanager.session() as session:
        email = input("User email: ")
        password = getpass(prompt="User password: ")
        user = UserSchema(
            id=uuid.uuid4(),
            email=email,
            password=password,
            created_at=datetime.now(UTC),
        )

        session.add(UserModel(**user.model_dump()))
        await session.commit()


if __name__ == "__main__":
    run(main())
