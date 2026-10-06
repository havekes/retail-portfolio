from typing import Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich import print as rprint

MIN_SECRET_KEY_LENGTH: int = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env",), extra="ignore")

    environment: str = "prod"
    log_level: str | None = None
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

    # Indicator Service
    indicator_service_url: str = "http://localhost:8080"

    # AI API
    ai_api_endpoint: str = "https://api.openai.com/v1/chat/completions"
    ai_api_key: str = ""
    ai_api_model: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    sync_ttl_seconds: int = 300

    # Observability / Metrics
    worker_metrics_port: int = 8004
    enable_metrics: bool = True

    # 2FA / TOTP
    totp_max_attempts: int = 5
    totp_lockout_seconds: int = 900

    # WebAuthn Passkeys
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Retail Portfolio"
    webauthn_origin: str = "http://localhost:8100"
    webauthn_challenge_ttl_seconds: int = 300

    # Email
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_sender_email: str = "noreply@retail-portfolio.local"
    email_verification_token_expiry_hours: int = 24

    # OpenTelemetry Observability
    otel_sdk_disabled: bool = False
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None
    deploy_id: str = "dev"
    service_version: str = "0.0.0"

    @field_validator("smtp_sender_email", mode="before")
    @classmethod
    def validate_smtp_sender_email(cls, v: str | None) -> str:
        if not v or (isinstance(v, str) and not v.strip()):
            return "noreply@retail-portfolio.local"
        return v

    @field_validator("otel_sdk_disabled", mode="before")
    @classmethod
    def validate_otel_sdk_disabled(cls, v: object) -> bool:
        if v is None or v == "":
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    @field_validator("deploy_id", mode="before")
    @classmethod
    def validate_deploy_id(cls, v: str | None) -> str:
        if not v or (isinstance(v, str) and not v.strip()):
            return "dev"
        return v

    @field_validator("service_version", mode="before")
    @classmethod
    def validate_service_version(cls, v: str | None) -> str:
        if not v or (isinstance(v, str) and not v.strip()):
            return "0.0.0"
        return v

    @model_validator(mode="after")
    def validate_secret_key(self) -> Self:
        if self.environment.lower() not in ("dev", "test") and (
            not self.secret_key or len(self.secret_key.strip()) < MIN_SECRET_KEY_LENGTH
        ):
            msg = (
                "SECRET_KEY must be set and at least 32 characters long "
                "when running outside dev/test environments. Generate a secure key "
                "with: openssl rand -hex 32 or python -c "
                '"import secrets; print(secrets.token_hex(32))"'
            )
            raise ValueError(msg)
        return self


settings = Settings()
