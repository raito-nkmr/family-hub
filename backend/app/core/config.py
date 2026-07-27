from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
DEFAULT_PHOTO_DERIVATIVE_ROOT = BACKEND_ENV_FILE.parent / "var" / "photo-derivatives"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=18000, ge=1, le=65535)
    app_reload: bool = False
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: str = "http://localhost:15173"
    database_url: str | None = None
    auth_trusted_origins: str = "http://localhost:15173"
    auth_session_idle_seconds: int = Field(default=604_800, gt=0)
    auth_session_absolute_seconds: int = Field(default=2_592_000, gt=0)
    auth_session_touch_seconds: int = Field(default=3_600, gt=0)
    auth_cookie_secure: bool = False
    auth_login_attempts: int = Field(default=5, gt=0)
    auth_login_window_seconds: int = Field(default=300, gt=0)
    auth_invitation_ttl_seconds: int = Field(default=86_400, gt=0)
    photo_storage_root: Path | None = None
    photo_storage_marker: str | None = None
    photo_derivative_root: Path = DEFAULT_PHOTO_DERIVATIVE_ROOT
    photo_max_upload_bytes: int | None = Field(default=None, gt=0)
    photo_min_free_bytes: int | None = Field(default=None, ge=0)
    photo_upload_chunk_bytes: int | None = Field(default=None, gt=0)
    photo_default_timezone: str = "Asia/Tokyo"
    photo_trash_retention_days: int = Field(default=30, ge=1, le=3650)
    backup_storage_root: Path | None = None
    backup_storage_marker: str | None = None
    push_vapid_public_key: str | None = None
    push_vapid_private_key_file: Path | None = None
    push_vapid_subject: str | None = None
    push_allowed_endpoint_hosts: str = "web.push.apple.com,fcm.googleapis.com,updates.push.services.mozilla.com"
    push_max_subscriptions_per_user: int = Field(default=10, ge=1, le=100)

    @field_validator("photo_default_timezone")
    @classmethod
    def validate_photo_default_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("PHOTO_DEFAULT_TIMEZONE must be a valid IANA timezone") from error
        return value

    @model_validator(mode="after")
    def validate_authentication_settings(self) -> "Settings":
        if self.auth_session_idle_seconds > self.auth_session_absolute_seconds:
            raise ValueError("AUTH_SESSION_IDLE_SECONDS must not exceed AUTH_SESSION_ABSOLUTE_SECONDS")
        if self.app_env == "production" and not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE must be true in production")
        if not self.auth_trusted_origin_list:
            raise ValueError("AUTH_TRUSTED_ORIGINS must contain at least one origin")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def auth_trusted_origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.auth_trusted_origins.split(",") if origin.strip()]

    @property
    def push_allowed_endpoint_host_list(self) -> list[str]:
        return [host.strip().lower() for host in self.push_allowed_endpoint_hosts.split(",") if host.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_management_settings() -> Settings:
    return Settings(_env_file=BACKEND_ENV_FILE)
