import logging
import time
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import request_id_context

REQUEST_ID_HEADER = b"x-request-id"
http_logger = logging.getLogger("app.http")


class RequestLoggingMiddleware:
    """Add a request ID and record safe request outcome metadata."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = str(uuid4())
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        status_code: int | None = None

        async def send_with_status(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self._app(scope, receive, send_with_status)
        except Exception:
            http_logger.exception(
                "Unhandled request exception method=%s path=%s",
                scope.get("method", "-"),
                scope.get("path", "-"),
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            if status_code is not None:
                level = logging.ERROR if status_code >= 500 else logging.WARNING if status_code >= 400 else logging.INFO
                http_logger.log(
                    level,
                    "HTTP request completed method=%s path=%s status=%d duration_ms=%.1f",
                    scope.get("method", "-"),
                    scope.get("path", "-"),
                    status_code,
                    duration_ms,
                )
            request_id_context.reset(token)


class PrivateApiCacheControlMiddleware:
    """Prevent browser and intermediary caching of API responses."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self._app(scope, receive, send)
            return

        async def send_with_cache_control(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["Cache-Control"] = "private, no-store"
            await send(message)

        await self._app(scope, receive, send_with_cache_control)
