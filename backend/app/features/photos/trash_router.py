from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.photos.dependencies import get_photo_service
from app.features.photos.schemas import PhotoResponse, TrashedPhotoListResponse
from app.features.photos.service import (
    InvalidTrashCursorError,
    PhotoContentUnavailableError,
    PhotoDeletePersistenceError,
    PhotoDeleteStorageError,
    PhotoNotFoundError,
    PhotoService,
)

router = APIRouter()


def _photo_response(photo, *, is_favorite: bool) -> PhotoResponse:
    return PhotoResponse.model_validate(photo).model_copy(
        update={
            "is_favorite": is_favorite,
            "captured_at": photo.metadata_record.captured_at_override or photo.captured_at,
            "captured_at_original": photo.captured_at,
            "captured_at_override": photo.metadata_record.captured_at_override,
        }
    )


@router.get("/trash", response_model=TrashedPhotoListResponse)
def list_trashed_photos(
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoService, Depends(get_photo_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
) -> TrashedPhotoListResponse:
    try:
        page = service.list_trashed_photos(authenticated_user.id, limit=limit, cursor=cursor)
    except InvalidTrashCursorError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trash cursor") from error
    return TrashedPhotoListResponse(
        items=[_photo_response(photo, is_favorite=photo.id in page.favorite_photo_ids) for photo in page.items],
        next_cursor=page.next_cursor,
        total_count=page.total_count,
    )


@router.get("/trash/{photo_id}/thumbnail", response_class=FileResponse)
def get_trashed_photo_thumbnail(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoService, Depends(get_photo_service)],
) -> FileResponse:
    try:
        content = service.get_trashed_photo_thumbnail(photo_id, authenticated_user.id)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoContentUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Photo thumbnail unavailable"
        ) from error
    return FileResponse(content.path, media_type=content.content_type, headers={"Cache-Control": "private, no-store"})


@router.delete("/{photo_id}", response_model=PhotoResponse, dependencies=[Depends(require_csrf_token)])
def trash_photo(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoService, Depends(get_photo_service)],
) -> PhotoResponse:
    try:
        photo = service.trash_photo(photo_id, authenticated_user.id)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoDeleteStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Photo storage unavailable"
        ) from error
    except PhotoDeletePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not trash photo"
        ) from error
    return _photo_response(photo, is_favorite=service.is_favorite(photo.id, authenticated_user.id))


@router.post("/{photo_id}/restore", response_model=PhotoResponse, dependencies=[Depends(require_csrf_token)])
def restore_photo(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoService, Depends(get_photo_service)],
) -> PhotoResponse:
    try:
        photo = service.restore_photo(photo_id, authenticated_user.id)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoDeleteStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Photo storage unavailable"
        ) from error
    except PhotoDeletePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not restore photo"
        ) from error
    return _photo_response(photo, is_favorite=service.is_favorite(photo.id, authenticated_user.id))


@router.delete(
    "/{photo_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def permanently_delete_photo(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoService, Depends(get_photo_service)],
) -> None:
    try:
        service.permanently_delete_photo(photo_id, authenticated_user.id)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoDeleteStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Photo deletion will be retried"
        ) from error
    except PhotoDeletePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete photo"
        ) from error
