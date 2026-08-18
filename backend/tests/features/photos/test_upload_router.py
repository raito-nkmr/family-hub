import threading
from unittest.mock import ANY, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect

from app.core.config import Settings
from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
)
from app.features.photos import upload_router as upload_router_module
from app.features.photos.dependencies import get_upload_batch_service
from app.features.photos.storage import StorageStatusCode
from app.features.photos.upload_router import _raise_upload_error, append_upload_chunk, get_upload_offset, router
from app.features.photos.uploads import UploadBatchStorageError, UploadOffsetError
from app.main import create_app


def test_upload_batch_routes_are_registered_in_openapi() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert "/api/v1/upload-batches" in paths
    assert "/api/v1/upload-batches/{batch_id}" in paths
    assert "/api/v1/upload-batches/items/{item_id}/content" in paths
    assert "/api/v1/upload-batches/items/{item_id}/complete" in paths


def test_upload_diagnostic_response_headers_are_exposed_to_lan_clients() -> None:
    app = create_app(Settings(app_env="test", cors_origins="http://192.0.2.10:15173"))
    user = AuthenticatedUser(id=uuid4(), username="owner")
    service = type("UploadServiceStub", (), {"get_offset": lambda self, requested, owner: 0})()
    app.dependency_overrides[require_authenticated_user] = lambda: user
    app.dependency_overrides[require_password_change_complete] = lambda: user
    app.dependency_overrides[get_upload_batch_service] = lambda: service

    response = TestClient(app).head(
        "/api/v1/upload-batches/items/00000000-0000-4000-8000-000000000001/content",
        headers={"Origin": "http://192.0.2.10:15173"},
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Expose-Headers"] == "Upload-Offset, X-Request-ID"


def test_upload_batch_router_requires_authentication_and_mutations_require_csrf() -> None:
    assert any(dependency.dependency is require_authenticated_user for dependency in router.dependencies)
    mutation_routes = [route for route in router.routes if route.methods & {"POST", "PATCH", "DELETE"}]
    assert mutation_routes
    assert all(
        any(dependency.dependency is require_csrf_token for dependency in route.dependencies)
        for route in mutation_routes
    )


def test_head_content_returns_resumable_offset() -> None:
    item_id = uuid4()
    user = AuthenticatedUser(id=uuid4(), username="owner")
    service = type("UploadServiceStub", (), {"get_offset": lambda self, requested, owner: 12})()
    response = get_upload_offset(item_id, user, service)

    assert response.status_code == 200
    assert response.headers["Upload-Offset"] == "12"


@pytest.mark.anyio
async def test_append_chunk_runs_sync_service_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    event_loop_thread = threading.get_ident()
    service_thread: int | None = None
    item_id = uuid4()
    attempt_id = uuid4()
    logger = MagicMock()
    monkeypatch.setattr(upload_router_module, "logger", logger)

    class RequestStub:
        headers = {
            "content-length": "5",
            "x-upload-attempt-id": str(attempt_id),
            "x-upload-retry-count": "1",
            "x-upload-route": "direct",
        }

        async def stream(self):
            yield b"chunk"

    class UploadServiceStub:
        def append_chunk(self, item_id, user_id, offset, payload):
            nonlocal service_thread
            service_thread = threading.get_ident()
            assert payload == b"chunk"
            return offset + len(payload)

    response = await append_upload_chunk(
        item_id,
        RequestStub(),
        0,
        AuthenticatedUser(id=uuid4(), username="owner"),
        UploadServiceStub(),
    )

    assert response.status_code == 200
    assert response.body == b"ok"
    assert response.headers["Content-Length"] == "2"
    assert response.headers["Upload-Offset"] == "5"
    assert service_thread is not None
    assert service_thread != event_loop_thread
    logger.info.assert_any_call(
        "Upload chunk receive started item_id=%s attempt_id=%s retry_count=%s route=%s expected_offset=%d "
        "content_length=%s",
        item_id,
        str(attempt_id),
        1,
        "direct",
        0,
        5,
    )
    logger.info.assert_any_call(
        "Upload chunk body received item_id=%s attempt_id=%s retry_count=%s route=%s expected_offset=%d "
        "received_bytes=%d duration_ms=%.1f",
        item_id,
        str(attempt_id),
        1,
        "direct",
        0,
        5,
        ANY,
    )
    logger.info.assert_any_call(
        "Upload chunk persisted item_id=%s attempt_id=%s retry_count=%s route=%s expected_offset=%d "
        "received_bytes=%d next_offset=%d duration_ms=%.1f",
        item_id,
        str(attempt_id),
        1,
        "direct",
        0,
        5,
        5,
        ANY,
    )


@pytest.mark.anyio
async def test_append_chunk_logs_client_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    item_id = uuid4()
    attempt_id = uuid4()
    logger = MagicMock()
    monkeypatch.setattr(upload_router_module, "logger", logger)

    class RequestStub:
        headers = {
            "content-length": "5",
            "x-upload-attempt-id": str(attempt_id),
            "x-upload-retry-count": "0",
            "x-upload-route": "direct",
        }

        async def stream(self):
            yield b"par"
            raise ClientDisconnect

    with pytest.raises(ClientDisconnect):
        await append_upload_chunk(
            item_id,
            RequestStub(),
            0,
            AuthenticatedUser(id=uuid4(), username="owner"),
            object(),
        )

    logger.warning.assert_called_once_with(
        "Upload chunk client disconnected item_id=%s attempt_id=%s retry_count=%s route=%s expected_offset=%d "
        "received_bytes=%d duration_ms=%.1f",
        item_id,
        str(attempt_id),
        0,
        "direct",
        0,
        3,
        ANY,
    )


@pytest.mark.parametrize(
    ("storage_status", "expected_status"),
    [
        (StorageStatusCode.INSUFFICIENT_SPACE, 507),
        (StorageStatusCode.NOT_MOUNT_POINT, 503),
        (None, 503),
    ],
)
def test_upload_storage_errors_preserve_insufficient_storage_status(
    storage_status: StorageStatusCode | None,
    expected_status: int,
) -> None:
    with pytest.raises(HTTPException) as caught:
        _raise_upload_error(UploadBatchStorageError(storage_status))

    assert caught.value.status_code == expected_status


def test_upload_offset_conflict_returns_the_actual_offset() -> None:
    with pytest.raises(HTTPException) as caught:
        _raise_upload_error(UploadOffsetError(8_388_608))

    assert caught.value.status_code == 409
    assert caught.value.headers == {"Upload-Offset": "8388608"}
