from pydantic import PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://retail-portfolio-user:password@localhost:5432/retail-portfolio"
    )
    echo_sql: bool = True


settings = Settings()  # pyright: ignore[reportCallIssue]
