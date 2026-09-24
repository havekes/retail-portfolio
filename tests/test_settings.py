import pytest
from pydantic import ValidationError

from src.config.settings import Settings


def test_settings_config_env_file():
    assert Settings.model_config["env_file"] == (".env",)


def test_settings_ignores_stray_src_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / ".env").write_text('ENVIRONMENT="staging"\n')

    s = Settings()
    assert s.environment == "prod"


def test_settings_loads_from_root_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text('ENVIRONMENT="dev"\n')

    s = Settings()
    assert s.environment == "dev"


def test_settings_defaults_when_no_env_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    s = Settings()
    assert s.environment == "prod"


def test_env_var_overrides_env_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "staging")

    (tmp_path / ".env").write_text('ENVIRONMENT="dev"\n')

    s = Settings()
    assert s.environment == "staging"


def test_smtp_sender_email_fallback_when_empty(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SMTP_SENDER_EMAIL", "")

    s = Settings()
    assert s.smtp_sender_email == "noreply@retail-portfolio.local"


def test_smtp_sender_email_custom_value(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SMTP_SENDER_EMAIL", "custom@example.com")

    s = Settings()
    assert s.smtp_sender_email == "custom@example.com"


def test_secret_key_required_in_prod(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_KEY", "")

    with pytest.raises(ValidationError, match="SECRET_KEY must be set and at least 32 characters long"):
        Settings()


def test_secret_key_too_short_in_prod(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_KEY", "short-key")

    with pytest.raises(ValidationError, match="SECRET_KEY must be set and at least 32 characters long"):
        Settings()


def test_secret_key_required_in_staging(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("SECRET_KEY", "")

    with pytest.raises(ValidationError, match="SECRET_KEY must be set and at least 32 characters long"):
        Settings()


def test_secret_key_allowed_empty_in_dev(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("SECRET_KEY", "")

    s = Settings()
    assert s.environment == "dev"
    assert s.secret_key == ""


def test_secret_key_allowed_empty_in_test(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("SECRET_KEY", "")

    s = Settings()
    assert s.environment == "test"
    assert s.secret_key == ""


def test_secret_key_valid_in_prod(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)

    s = Settings()
    assert s.environment == "prod"
    assert s.secret_key == "a" * 32


def test_service_token_required_in_prod(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("MARKET_DATA_SERVICE_TOKEN", "")

    with pytest.raises(
        ValidationError, match="MARKET_DATA_SERVICE_TOKEN must be set"
    ):
        Settings()


def test_service_token_whitespace_only_in_prod(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("MARKET_DATA_SERVICE_TOKEN", "   ")

    with pytest.raises(
        ValidationError, match="MARKET_DATA_SERVICE_TOKEN must be set"
    ):
        Settings()


def test_service_token_required_in_staging(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("MARKET_DATA_SERVICE_TOKEN", "")

    with pytest.raises(
        ValidationError, match="MARKET_DATA_SERVICE_TOKEN must be set"
    ):
        Settings()


def test_service_token_allowed_empty_in_dev(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("MARKET_DATA_SERVICE_TOKEN", "")

    s = Settings()
    assert s.environment == "dev"
    assert s.market_data_service_token == ""


def test_service_token_allowed_empty_in_test(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("MARKET_DATA_SERVICE_TOKEN", "")

    s = Settings()
    assert s.environment == "test"
    assert s.market_data_service_token == ""


def test_service_token_valid_in_prod(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("MARKET_DATA_SERVICE_TOKEN", "a" * 64)

    s = Settings()
    assert s.environment == "prod"
    assert s.market_data_service_token == "a" * 64


