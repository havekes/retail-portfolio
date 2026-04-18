from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    environment: str = "prod"
    secret_key: str = ""

    # Frontend URL
    frontend_url: str = "http://localhost:8101"

    # Debug/local
    stub_external_api: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://retail-portfolio-user:password@localhost:5432/retail-portfolio"
    echo_sql: bool = False

    # Cors
    cors_allow_origins: str = "http://localhost:8100"
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"

    # File uploads
    upload_path: str = "data/uploads"

    # Market API (Eodhd)
    eodhd_api_key: str = ""

    # AI API
    ai_api_endpoint: str = "https://api.openai.com/v1/chat/completions"
    ai_api_key: str = ""
    ai_api_model: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Email
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_sender_email: str = "noreply@retail-portfolio.com"
    email_verification_token_expiry_hours: int = 24


settings = Settings()
