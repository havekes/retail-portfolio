from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    envrionement: str = "dev"
    database_url: str = "postgresql+asyncpg://retail-portfolio-user:password@localhost:5432/retail-portfolio"
    echo_sql: bool = True
    secret_key: str = ""
    cors_allow_origins: str = "http://localhost:8100"
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"


settings = Settings()
