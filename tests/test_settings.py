import os
from pathlib import Path

from src.config.settings import Settings


def test_settings_config_env_file():
    assert Settings.model_config["env_file"] == (".env", "src/.env")


def test_settings_loads_from_src_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    env_file = src_dir / ".env"
    env_file.write_text('ENVIRONMENT="dev"\n')

    s = Settings()
    assert s.environment == "dev"


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

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / ".env").write_text('ENVIRONMENT="dev"\n')

    s = Settings()
    assert s.environment == "staging"
