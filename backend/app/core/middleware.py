import logging
import time
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import request_id_context

SINGLE_PHOTO_MULTIPART_OVERHEAD_BYTES = 64 * 1024
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


class SinglePhotoUploadSizeLimitMiddleware:
    """Reject oversized legacy multipart uploads before Starlette parses the body."""

    def __init__(self, app: ASGIApp, maximum_upload_bytes: int | None) -> None:
        self._app = app
        self._maximum_request_bytes = (
            maximum_upload_bytes + SINGLE_PHOTO_MULTIPART_OVERHEAD_BYTES if maximum_upload_bytes is not None else None
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._is_limited_request(scope):
            await self._app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._maximum_request_bytes:
                    await self._send_too_large(scope, receive, send)
                    return
            except ValueError:
                pass

        received_bytes = 0
        request_too_large = False
        response_messages = []

        async def receive_with_limit():
            nonlocal received_bytes, request_too_large
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self._maximum_request_bytes:
                    request_too_large = True
                    raise _RequestTooLarge
            return message

        async def buffer_response(message):
            response_messages.append(message)

        try:
            await self._app(scope, receive_with_limit, buffer_response)
        except _RequestTooLarge:
            request_too_large = True

        if request_too_large:
            await self._send_too_large(scope, receive, send)
            return
        for message in response_messages:
            await send(message)

    def _is_limited_request(self, scope: Scope) -> bool:
        return bool(
            self._maximum_request_bytes is not None
            and scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] == "/api/v1/photos"
        )

    @staticmethod
    async def _send_too_large(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": "Photo is too large"},
        )
        await response(scope, receive, send)


class _RequestTooLarge(Exception):
    """Stop request-body parsing once the configured byte limit is crossed."""
