from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings
from app.core.logging import configure_logging
from app.features.auth.rate_limit import LoginRateLimiter


def create_lifespan(settings: Settings) -> Callable[[FastAPI], AsyncIterator[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.app_log_level)
        app.state.settings = settings
        app.state.login_rate_limiter = LoginRateLimiter(
            maximum_attempts=settings.auth_login_attempts,
            window_seconds=settings.auth_login_window_seconds,
        )
        yield

    return lifespan
