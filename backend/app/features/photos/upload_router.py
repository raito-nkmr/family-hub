import logging
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
)
from app.features.photos.dependencies import get_upload_batch_service
from app.features.photos.models import UploadBatch, UploadItem
from app.features.photos.schemas import UploadBatchCreate, UploadBatchResponse, UploadItemResponse
from app.features.photos.storage import StorageStatusCode
from app.features.photos.uploads import (
    MAX_UPLOAD_CHUNK_BYTES,
    UploadBatchInvalidError,
    UploadBatchNotFoundError,
    UploadBatchPersistenceError,
    UploadBatchService,
    UploadBatchStorageError,
    UploadChunkTooLargeError,
    UploadItemNotFoundError,
    UploadOffsetError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["photo uploads"],
    dependencies=[Depends(require_authenticated_user), Depends(require_password_change_complete)],
)


def _item_response(item: UploadItem) -> UploadItemResponse:
    return UploadItemResponse(
        id=item.id,
        client_id=item.client_id,
        original_filename=item.original_filename,
        declared_content_type=item.declared_content_type,
        size_bytes=item.size_bytes,
        received_bytes=item.received_bytes,
        status=item.status,
        error_code=item.error_code,
        photo_id=item.photo_id,
    )


def _batch_response(batch: UploadBatch, items: list[UploadItem]) -> UploadBatchResponse:
    return UploadBatchResponse(
        id=batch.id,
        status=batch.status,
        visibility=batch.visibility,
        group_ids=batch.group_ids,
        created_at=batch.created_at,
        expires_at=batch.expires_at,
        completed_at=batch.completed_at,
        items=[_item_response(item) for item in items],
    )


def _raise_upload_error(error: Exception) -> None:
    if isinstance(error, (UploadBatchNotFoundError, UploadItemNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found") from error
    if isinstance(error, UploadOffsetError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload offset mismatch",
            headers={"Upload-Offset": str(error.actual_offset)},
        ) from error
    if isinstance(error, (UploadBatchInvalidError, UploadChunkTooLargeError)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid upload") from error
    if isinstance(error, UploadBatchStorageError):
        if error.storage_status is StorageStatusCode.INSUFFICIENT_SPACE:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail="Insufficient storage",
            ) from error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage unavailable",
        ) from error
    if isinstance(error, UploadBatchPersistenceError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update upload",
        ) from error
    raise error


@router.post(
    "",
    response_model=UploadBatchResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_upload_batch(
    body: UploadBatchCreate,
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[UploadBatchService, Depends(get_upload_batch_service)],
) -> UploadBatchResponse:
    try:
        return _batch_response(*service.create_batch(user.id, body.files, set(body.sharing.group_ids)))
    except (UploadBatchInvalidError, UploadBatchStorageError, UploadBatchPersistenceError) as error:
        _raise_upload_error(error)


@router.get("/{batch_id}", response_model=UploadBatchResponse)
def get_upload_batch(
    batch_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[UploadBatchService, Depends(get_upload_batch_service)],
) -> UploadBatchResponse:
    try:
        return _batch_response(*service.get_batch(batch_id, user.id))
    except UploadBatchNotFoundError as error:
        _raise_upload_error(error)


@router.delete(
    "/{batch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def cancel_upload_batch(
    batch_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[UploadBatchService, Depends(get_upload_batch_service)],
) -> Response:
    try:
        service.cancel_batch(batch_id, user.id)
    except (UploadBatchNotFoundError, UploadBatchPersistenceError) as error:
        _raise_upload_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.head("/items/{item_id}/content")
def get_upload_offset(
    item_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[UploadBatchService, Depends(get_upload_batch_service)],
) -> Response:
    try:
        offset = service.get_offset(item_id, user.id)
    except (UploadItemNotFoundError, UploadBatchPersistenceError, UploadBatchStorageError) as error:
        _raise_upload_error(error)
    logger.info("Upload offset read item_id=%s offset=%d", item_id, offset)
    return Response(headers={"Upload-Offset": str(offset)})


def _upload_diagnostic_headers(request: Request) -> tuple[str, int | None, str]:
    raw_attempt_id = request.headers.get("x-upload-attempt-id")
    try:
        attempt_id = str(UUID(raw_attempt_id)) if raw_attempt_id is not None else "-"
    except ValueError:
        attempt_id = "-"

    raw_retry_count = request.headers.get("x-upload-retry-count", "")
    retry_count = int(raw_retry_count) if raw_retry_count.isdigit() else None
    if retry_count is not None and not 0 <= retry_count <= 100:
        retry_count = None

    raw_route = request.headers.get("x-upload-route")
    upload_route = raw_route if raw_route in {"direct", "same-origin"} else "unknown"
    return attempt_id, retry_count, upload_route


def _content_length(request: Request) -> int | None:
    raw_content_length = request.headers.get("content-length", "")
    return int(raw_content_length) if raw_content_length.isdigit() else None


@router.patch(
    "/items/{item_id}/content",
    status_code=status.HTTP_200_OK,
    response_class=PlainTextResponse,
    dependencies=[Depends(require_csrf_token)],
)
async def append_upload_chunk(
    item_id: UUID,
    request: Request,
    upload_offset: Annotated[int, Header(alias="Upload-Offset")],
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[UploadBatchService, Depends(get_upload_batch_service)],
) -> Response:
    attempt_id, retry_count, upload_route = _upload_diagnostic_headers(request)
    received_bytes = 0
    receive_started = time.perf_counter()
    logger.info(
        "Upload chunk receive started item_id=%s attempt_id=%s retry_count=%s route=%s expected_offset=%d "
        "content_length=%s",
        item_id,
        attempt_id,
        retry_count,
        upload_route,
        upload_offset,
        _content_length(request),
    )
    payload = bytearray()
    try:
        async for chunk in request.stream():
            payload.extend(chunk)
            received_bytes += len(chunk)
            if len(payload) > MAX_UPLOAD_CHUNK_BYTES:
                logger.warning(
                    "Upload chunk receive rejected item_id=%s attempt_id=%s retry_count=%s route=%s "
                    "expected_offset=%d received_bytes=%d reason=chunk_too_large duration_ms=%.1f",
                    item_id,
                    attempt_id,
                    retry_count,
                    upload_route,
                    upload_offset,
                    received_bytes,
                    (time.perf_counter() - receive_started) * 1000,
                )
                _raise_upload_error(UploadChunkTooLargeError())
    except ClientDisconnect:
        logger.warning(
            "Upload chunk client disconnected item_id=%s attempt_id=%s retry_count=%s route=%s expected_offset=%d "
            "received_bytes=%d duration_ms=%.1f",
            item_id,
            attempt_id,
            retry_count,
            upload_route,
            upload_offset,
            received_bytes,
            (time.perf_counter() - receive_started) * 1000,
        )
        raise
    logger.info(
        "Upload chunk body received item_id=%s attempt_id=%s retry_count=%s route=%s expected_offset=%d "
        "received_bytes=%d duration_ms=%.1f",
        item_id,
        attempt_id,
        retry_count,
        upload_route,
        upload_offset,
        received_bytes,
        (time.perf_counter() - receive_started) * 1000,
    )
    persist_started = time.perf_counter()
    try:
        next_offset = await run_in_threadpool(service.append_chunk, item_id, user.id, upload_offset, bytes(payload))
    except (
        UploadItemNotFoundError,
        UploadBatchInvalidError,
        UploadChunkTooLargeError,
        UploadOffsetError,
        UploadBatchStorageError,
        UploadBatchPersistenceError,
    ) as error:
        logger.warning(
            "Upload chunk persist rejected item_id=%s attempt_id=%s retry_count=%s route=%s expected_offset=%d "
            "received_bytes=%d error_type=%s actual_offset=%s duration_ms=%.1f",
            item_id,
            attempt_id,
            retry_count,
            upload_route,
            upload_offset,
            received_bytes,
            type(error).__name__,
            error.actual_offset if isinstance(error, UploadOffsetError) else None,
            (time.perf_counter() - persist_started) * 1000,
        )
        _raise_upload_error(error)
    logger.info(
        "Upload chunk persisted item_id=%s attempt_id=%s retry_count=%s route=%s expected_offset=%d "
        "received_bytes=%d next_offset=%d duration_ms=%.1f",
        item_id,
        attempt_id,
        retry_count,
        upload_route,
        upload_offset,
        received_bytes,
        next_offset,
        (time.perf_counter() - persist_started) * 1000,
    )
    return PlainTextResponse("ok", headers={"Upload-Offset": str(next_offset)})


@router.post(
    "/items/{item_id}/complete",
    response_model=UploadItemResponse,
    dependencies=[Depends(require_csrf_token)],
)
def complete_upload_item(
    item_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[UploadBatchService, Depends(get_upload_batch_service)],
) -> UploadItemResponse:
    try:
        return _item_response(service.complete_item(item_id, user.id, user.username))
    except (
        UploadItemNotFoundError,
        UploadBatchInvalidError,
        UploadOffsetError,
        UploadBatchStorageError,
        UploadBatchPersistenceError,
    ) as error:
        _raise_upload_error(error)
