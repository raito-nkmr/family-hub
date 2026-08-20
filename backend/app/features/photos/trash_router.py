from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.photos.access_service import PhotoAccessService
from app.features.photos.dependencies import get_photo_access_service, get_photo_trash_service
from app.features.photos.schemas import PhotoResponse, TrashedPhotoListResponse, photo_response_from_model
from app.features.photos.service import (
    InvalidTrashCursorError,
    PhotoContentUnavailableError,
    PhotoDeletePersistenceError,
    PhotoDeleteStorageError,
    PhotoNotFoundError,
    PhotoPurgeNotDueError,
)
from app.features.photos.trash_service import PhotoTrashService

router = APIRouter()


def _photo_response(photo, *, is_favorite: bool, visible_group_ids: set[UUID]) -> PhotoResponse:
    return photo_response_from_model(photo, visible_group_ids=visible_group_ids, is_favorite=is_favorite)


@router.get("/trash", response_model=TrashedPhotoListResponse)
def list_trashed_photos(
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoTrashService, Depends(get_photo_trash_service)],
    access_service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
) -> TrashedPhotoListResponse:
    try:
        page = service.list_trashed_photos(authenticated_user.id, limit=limit, cursor=cursor)
    except InvalidTrashCursorError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trash cursor") from error
    visible_group_ids = access_service.visible_share_group_ids(
        {photo.id for photo in page.items}, authenticated_user.id
    )
    return TrashedPhotoListResponse(
        items=[
            _photo_response(
                photo,
                is_favorite=photo.id in page.favorite_photo_ids,
                visible_group_ids=visible_group_ids.get(photo.id, set()),
            )
            for photo in page.items
        ],
        next_cursor=page.next_cursor,
        total_count=page.total_count,
    )


@router.get("/trash/{photo_id}/thumbnail", response_class=FileResponse)
def get_trashed_photo_thumbnail(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoTrashService, Depends(get_photo_trash_service)],
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
    service: Annotated[PhotoTrashService, Depends(get_photo_trash_service)],
    access_service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
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
    visible_group_ids = access_service.visible_share_group_ids({photo.id}, authenticated_user.id)
    return _photo_response(
        photo,
        is_favorite=access_service.is_favorite(photo.id, authenticated_user.id),
        visible_group_ids=visible_group_ids.get(photo.id, set()),
    )


@router.post("/{photo_id}/restore", response_model=PhotoResponse, dependencies=[Depends(require_csrf_token)])
def restore_photo(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoTrashService, Depends(get_photo_trash_service)],
    access_service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
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
    visible_group_ids = access_service.visible_share_group_ids({photo.id}, authenticated_user.id)
    return _photo_response(
        photo,
        is_favorite=access_service.is_favorite(photo.id, authenticated_user.id),
        visible_group_ids=visible_group_ids.get(photo.id, set()),
    )


@router.delete(
    "/{photo_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def permanently_delete_photo(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoTrashService, Depends(get_photo_trash_service)],
) -> None:
    try:
        service.permanently_delete_photo(photo_id, authenticated_user.id)
    except PhotoPurgeNotDueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Photo retention period has not elapsed",
        ) from error
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
