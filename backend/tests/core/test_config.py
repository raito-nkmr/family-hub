import pytest
from pydantic import ValidationError

from app.core import config as config_module
from app.core.config import Settings, get_management_settings, get_settings


def test_cors_origin_list_parses_comma_separated_origins() -> None:
    settings = Settings(cors_origins="http://localhost:5173, https://photos.example.test")

    assert settings.cors_origin_list == ["http://localhost:5173", "https://photos.example.test"]


def test_app_port_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        Settings(app_port=0)


def test_default_app_port_is_separate_from_production() -> None:
    assert Settings().app_port == 8001


def test_photo_default_timezone_must_be_valid() -> None:
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        Settings(photo_default_timezone="not/a-timezone")


def test_settings_require_secure_authentication_cookie_in_production() -> None:
    with pytest.raises(ValidationError, match="AUTH_COOKIE_SECURE must be true"):
        Settings(app_env="production", auth_cookie_secure=False)


def test_settings_reject_session_idle_timeout_longer_than_absolute_timeout() -> None:
    with pytest.raises(ValidationError, match="AUTH_SESSION_IDLE_SECONDS"):
        Settings(auth_session_idle_seconds=20, auth_session_absolute_seconds=10)


def test_management_settings_load_database_url_from_explicit_env_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql+psycopg://user:password@localhost/database\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "BACKEND_ENV_FILE", env_file)

    settings = get_management_settings()

    assert settings.database_url == "postgresql+psycopg://user:password@localhost/database"


def test_application_settings_require_environment_to_be_loaded_by_process(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql+psycopg://ignored/database\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "BACKEND_ENV_FILE", env_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.database_url is None
