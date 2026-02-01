from asyncio import run
from datetime import UTC, datetime, timedelta

import jwt
from rich import print as rprint

from src.auth.api_types import AccessTokenData
from src.auth.model import UserModel
from src.config.database import sessionmanager
from src.config.settings import settings


async def main():
    async with sessionmanager.session():
        email = input("User email: ")

        access_token_data = AccessTokenData(
            sub=email,
            exp=int((datetime.now(UTC) + timedelta(days=365)).timestamp()),
        )

        rprint(
            jwt.encode(
                access_token_data.model_dump(),
                settings.secret_key,
                algorithm="HS256",
            )
        )


if __name__ == "__main__":
    run(main())
