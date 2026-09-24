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

    # Market API (FMP)
    fmp_api_key: str = ""

    # Market API (Polygon)
    polygon_api_key: str = ""

    # Indicator Service
    indicator_service_url: str = "http://localhost:8080"

    # Service-to-service auth (MCP gateway -> data endpoints), sent as X-Service-Token
    market_data_service_token: str = ""

    # AI API
    ai_api_endpoint: str = "https://api.openai.com/v1/chat/completions"
    ai_api_key: str = ""
    ai_api_model: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    sync_ttl_seconds: int = 300

    # Market gateway cache TTLs (seconds), per data class
    gateway_ttl_search_seconds: int = 1_209_600  # 14 days
    gateway_ttl_prices_seconds: int = 3_600  # 1 hour (daily + intraday)
    gateway_ttl_statements_seconds: int = 86_400  # 1 day
    gateway_ttl_metrics_seconds: int = 86_400  # 1 day (incl. profile / lookup)
    gateway_ttl_options_seconds: int = 1_800  # 30 minutes

    # Endpoint-level response cache TTLs (seconds), per data class
    endpoint_ttl_prices_seconds: int = 3_600  # 1 hour
    endpoint_ttl_statements_seconds: int = 86_400  # 1 day
    endpoint_ttl_metrics_seconds: int = 86_400  # 1 day
    endpoint_ttl_options_seconds: int = 1_800  # 30 minutes
    endpoint_ttl_search_seconds: int = 3_600  # 1 hour (symbol lookup)

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

    @field_validator("smtp_sender_email", mode="before")
    @classmethod
    def validate_smtp_sender_email(cls, v: str | None) -> str:
        if not v or (isinstance(v, str) and not v.strip()):
            return "noreply@retail-portfolio.local"
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

    @model_validator(mode="after")
    def validate_service_token(self) -> Self:
        if self.environment.lower() not in ("dev", "test") and (
            not self.market_data_service_token
            or not self.market_data_service_token.strip()
        ):
            msg = (
                "MARKET_DATA_SERVICE_TOKEN must be set when running outside "
                "dev/test environments. Generate a secure token with: "
                "openssl rand -hex 32 or python -c "
                '"import secrets; print(secrets.token_hex(32))"'
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_market_provider_keys(self) -> Self:
        """Require the data-plane provider keys outside dev/test.

        The provider-agnostic data-plane gateway routes prices/fundamentals to
        FMP and options to Polygon, so both keys are required whenever real
        providers are used. Dev/test and stub mode (``STUB_EXTERNAL_API=true``)
        are exempt: the stub gateways are offline and need no credentials.
        """
        if self.environment.lower() in ("dev", "test") or self.stub_external_api:
            return self

        missing = [
            name
            for name, value in (
                ("FMP_API_KEY", self.fmp_api_key),
                ("POLYGON_API_KEY", self.polygon_api_key),
            )
            if not value or not value.strip()
        ]
        if missing:
            msg = " ".join(
                f"{name} must be set when running outside dev/test environments "
                "with stub mode disabled (or set STUB_EXTERNAL_API=true to use "
                "the offline stub gateway)."
                for name in missing
            )
            raise ValueError(msg)
        return self


settings = Settings()
