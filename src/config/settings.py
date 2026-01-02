from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    envrionement: str = "dev"
    database_url: str = "postgresql+asyncpg://retail-portfolio-user:password@localhost:5432/retail-portfolio"
    echo_sql: bool = True


settings = Settings()  # pyright: ignore[reportCallIssue]
