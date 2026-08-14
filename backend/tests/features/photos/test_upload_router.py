import threading
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.photos.storage import StorageStatusCode
from app.features.photos.upload_router import _raise_upload_error, append_upload_chunk, get_upload_offset, router
from app.features.photos.uploads import UploadBatchStorageError
from app.main import create_app


def test_upload_batch_routes_are_registered_in_openapi() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert "/api/v1/upload-batches" in paths
    assert "/api/v1/upload-batches/{batch_id}" in paths
    assert "/api/v1/upload-batches/items/{item_id}/content" in paths
    assert "/api/v1/upload-batches/items/{item_id}/complete" in paths


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
async def test_append_chunk_runs_sync_service_off_the_event_loop() -> None:
    event_loop_thread = threading.get_ident()
    service_thread: int | None = None

    class RequestStub:
        async def stream(self):
            yield b"chunk"

    class UploadServiceStub:
        def append_chunk(self, item_id, user_id, offset, payload):
            nonlocal service_thread
            service_thread = threading.get_ident()
            assert payload == b"chunk"
            return offset + len(payload)

    response = await append_upload_chunk(
        uuid4(),
        RequestStub(),
        0,
        AuthenticatedUser(id=uuid4(), username="owner"),
        UploadServiceStub(),
    )

    assert response.status_code == 204
    assert response.headers["Upload-Offset"] == "5"
    assert service_thread is not None
    assert service_thread != event_loop_thread


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
