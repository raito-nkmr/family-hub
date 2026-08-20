from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.features.auth.dependencies import (
    AuthenticatedUser,
    get_auth_service,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
)
from app.features.auth.public import AuthService, InvalidCurrentPasswordError
from app.features.photos.access_service import PhotoAccessService
from app.features.photos.activity import (
    InvalidPhotoActivityCursorError,
    PhotoActivityNotFoundError,
    PhotoActivityPersistenceError,
    PhotoActivityService,
)
from app.features.photos.dependencies import (
    get_photo_access_service,
    get_photo_activity_service,
    get_photo_metadata_service,
    get_photo_query_service,
    get_photo_storage,
)
from app.features.photos.errors import (
    InvalidPhotoSharingError,
    PhotoBulkSelectionError,
    PhotoContentUnavailableError,
    PhotoNotFoundError,
    PhotoUpdateConflictError,
    PhotoUpdateForbiddenError,
    PhotoUpdatePersistenceError,
    PhotoUpdateStorageError,
)
from app.features.photos.export_router import router as export_router
from app.features.photos.metadata_service import PhotoMetadataService
from app.features.photos.models import Photo
from app.features.photos.queries import (
    InvalidPhotoCursorError,
    PhotoAlbumNotFoundError,
    PhotoListFilters,
    PhotoQueryService,
)
from app.features.photos.schemas import (
    BulkPhotoSharingAdd,
    BulkPhotoSharingResponse,
    GroupPhotoModerationRequest,
    PhotoActivityItemResponse,
    PhotoActivityResponse,
    PhotoActivitySeenUpdate,
    PhotoListItemResponse,
    PhotoListQuery,
    PhotoListResponse,
    PhotoResponse,
    PhotoSearchOptionResponse,
    PhotoSearchOptionsResponse,
    PhotoTimelineMonthResponse,
    PhotoTimelineResponse,
    PhotoUpdate,
    StorageStatusResponse,
    photo_response_from_model,
)
from app.features.photos.storage import PhotoStorage
from app.features.photos.trash_router import router as trash_router

router = APIRouter(
    tags=["photos"],
    dependencies=[Depends(require_authenticated_user), Depends(require_password_change_complete)],
)
router.include_router(export_router)
router.include_router(trash_router)


def _photo_response(photo: Photo, service: PhotoAccessService, user_id: UUID) -> PhotoResponse:
    visible_group_ids = service.visible_share_group_ids({photo.id}, user_id).get(photo.id, set())
    return photo_response_from_model(
        photo,
        visible_group_ids=visible_group_ids,
        is_favorite=service.is_favorite(photo.id, user_id),
    )


@router.get("/storage-status", response_model=StorageStatusResponse)
async def get_storage_status(storage: Annotated[PhotoStorage, Depends(get_photo_storage)]) -> StorageStatusResponse:
    status = storage.get_status()
    return StorageStatusResponse(
        status=status.status,
        available=status.available,
        writable=status.writable,
        free_bytes=status.free_bytes,
        minimum_free_bytes=status.minimum_free_bytes,
        total_bytes=status.total_bytes,
    )


@router.get("", response_model=PhotoListResponse)
def list_photo_metadata(
    filters: Annotated[PhotoListQuery, Query()],
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoQueryService, Depends(get_photo_query_service)],
) -> PhotoListResponse:
    uploader_id = authenticated_user.id if filters.mine_only else filters.uploader_id
    try:
        page = service.list_photos(
            authenticated_user.id,
            PhotoListFilters(
                limit=filters.limit,
                cursor=filters.cursor,
                keyword=filters.q,
                date_from=filters.date_from,
                date_to=filters.date_to,
                uploader_id=uploader_id,
                visibility=filters.visibility,
                captured_at_known=filters.captured_at_known,
                album_id=filters.album_id,
                exclude_album_id=filters.exclude_album_id,
                sharing_group_id=filters.sharing_group_id,
                favorite=filters.favorite,
            ),
        )
    except PhotoAlbumNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found") from error
    except InvalidPhotoCursorError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid photo cursor") from error
    return PhotoListResponse(
        items=[PhotoListItemResponse.model_validate(photo) for photo in page.items],
        next_cursor=page.next_cursor,
        total_count=page.total_count,
    )


@router.get("/search-options", response_model=PhotoSearchOptionsResponse)
def get_photo_search_options(
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoQueryService, Depends(get_photo_query_service)],
) -> PhotoSearchOptionsResponse:
    options = service.search_options(authenticated_user.id)
    return PhotoSearchOptionsResponse(
        uploaders=[
            PhotoSearchOptionResponse.model_validate(option, from_attributes=True) for option in options.uploaders
        ],
        groups=[PhotoSearchOptionResponse.model_validate(option, from_attributes=True) for option in options.groups],
    )


@router.get("/timeline", response_model=PhotoTimelineResponse)
def get_photo_timeline(
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoQueryService, Depends(get_photo_query_service)],
    year: Annotated[int, Query(ge=1, le=9998)],
) -> PhotoTimelineResponse:
    months = service.timeline(authenticated_user.id, year)
    return PhotoTimelineResponse(
        year=year,
        months=[PhotoTimelineMonthResponse.model_validate(month, from_attributes=True) for month in months],
    )


@router.get("/activity", response_model=PhotoActivityResponse)
def list_photo_activity(
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoActivityService, Depends(get_photo_activity_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
) -> PhotoActivityResponse:
    try:
        page = service.list_activity(authenticated_user.id, limit=limit, cursor=cursor)
    except InvalidPhotoActivityCursorError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid photo activity cursor") from error
    return PhotoActivityResponse(
        items=[PhotoActivityItemResponse.model_validate(item, from_attributes=True) for item in page.items],
        next_cursor=page.next_cursor,
        unseen_count=page.unseen_count,
    )


@router.post(
    "/activity/seen",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def mark_photo_activity_seen(
    body: PhotoActivitySeenUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoActivityService, Depends(get_photo_activity_service)],
) -> None:
    try:
        service.mark_seen(authenticated_user.id, body.event_id)
    except PhotoActivityNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo activity not found") from error
    except PhotoActivityPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update photo activity",
        ) from error


@router.post(
    "/bulk-sharing",
    response_model=BulkPhotoSharingResponse,
    dependencies=[Depends(require_csrf_token)],
)
def bulk_add_photo_sharing(
    body: BulkPhotoSharingAdd,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoMetadataService, Depends(get_photo_metadata_service)],
) -> BulkPhotoSharingResponse:
    try:
        result = service.bulk_add_sharing(
            body.photo_ids,
            set(body.add_group_ids),
            authenticated_user.id,
            authenticated_user.username,
        )
    except PhotoBulkSelectionError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more photos were not found",
        ) from error
    except InvalidPhotoSharingError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Photo group is not available") from error
    except PhotoUpdatePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update photo sharing",
        ) from error
    except PhotoUpdateStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage unavailable",
        ) from error
    return BulkPhotoSharingResponse.model_validate(result, from_attributes=True)


@router.get("/{photo_id}", response_model=PhotoResponse)
def get_photo_metadata(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
) -> PhotoResponse:
    try:
        photo = service.get_photo(photo_id, authenticated_user.id)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    return _photo_response(photo, service, authenticated_user.id)


@router.get("/{photo_id}/content", response_class=FileResponse)
def get_photo_content(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
) -> FileResponse:
    try:
        content = service.get_photo_content(photo_id, authenticated_user.id)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoContentUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo content unavailable",
        ) from error
    return FileResponse(
        content.path,
        media_type=content.content_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{photo_id}/download", response_class=FileResponse)
def download_photo_original(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
) -> FileResponse:
    try:
        photo = service.get_photo(photo_id, authenticated_user.id)
        content = service.get_photo_content(photo_id, authenticated_user.id)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoContentUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo content unavailable",
        ) from error
    return FileResponse(
        content.path,
        media_type=content.content_type,
        filename=photo.original_filename,
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{photo_id}/thumbnail", response_class=FileResponse)
def get_photo_thumbnail(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
) -> FileResponse:
    try:
        content = service.get_photo_thumbnail(photo_id, authenticated_user.id)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoContentUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo thumbnail unavailable",
        ) from error
    return FileResponse(
        content.path,
        media_type=content.content_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.patch(
    "/{photo_id}",
    response_model=PhotoResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_photo_metadata(
    photo_id: UUID,
    body: PhotoUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoMetadataService, Depends(get_photo_metadata_service)],
    access_service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
) -> PhotoResponse:
    try:
        update_kwargs = {
            "memo": body.memo,
            "update_memo": "memo" in body.model_fields_set,
            "sharing_group_ids": set(body.sharing.group_ids) if body.sharing is not None else None,
            "expected_version": body.version,
        }
        if "captured_at_override" in body.model_fields_set:
            update_kwargs.update(
                captured_at_override=body.captured_at_override,
                update_captured_at_override=True,
            )
        photo = service.update_photo(
            photo_id,
            authenticated_user.id,
            authenticated_user.username,
            **update_kwargs,
        )
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoUpdateForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the uploader can update photo sharing",
        ) from error
    except InvalidPhotoSharingError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Photo group is not available") from error
    except PhotoUpdateConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Photo metadata was updated by another request",
        ) from error
    except PhotoUpdatePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update photo metadata",
        ) from error
    except PhotoUpdateStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage unavailable",
        ) from error
    return _photo_response(photo, access_service, authenticated_user.id)


@router.delete(
    "/{photo_id}/groups/{group_id}",
    response_model=PhotoResponse,
    dependencies=[Depends(require_csrf_token)],
)
def remove_photo_group_share_as_admin(
    photo_id: UUID,
    group_id: UUID,
    body: GroupPhotoModerationRequest,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    photo_service: Annotated[PhotoMetadataService, Depends(get_photo_metadata_service)],
    access_service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
) -> PhotoResponse:
    try:
        auth_service.verify_current_password(authenticated_user.id, body.current_password)
        photo = photo_service.remove_group_share_as_admin(
            photo_id,
            group_id,
            authenticated_user.id,
            authenticated_user.username,
        )
    except InvalidCurrentPasswordError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current password is incorrect") from error
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo share not found") from error
    except PhotoUpdateForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group administrator required") from error
    except PhotoUpdateStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage unavailable",
        ) from error
    except PhotoUpdatePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update photo",
        ) from error
    return _photo_response(photo, access_service, authenticated_user.id)


@router.put(
    "/{photo_id}/favorite",
    response_model=PhotoResponse,
    dependencies=[Depends(require_csrf_token)],
)
def add_photo_favorite(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
) -> PhotoResponse:
    try:
        photo = service.set_favorite(photo_id, authenticated_user.id, True)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoUpdatePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update photo favorite",
        ) from error
    return _photo_response(photo, service, authenticated_user.id)


@router.delete(
    "/{photo_id}/favorite",
    response_model=PhotoResponse,
    dependencies=[Depends(require_csrf_token)],
)
def remove_photo_favorite(
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoAccessService, Depends(get_photo_access_service)],
) -> PhotoResponse:
    try:
        photo = service.set_favorite(photo_id, authenticated_user.id, False)
    except PhotoNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    except PhotoUpdatePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update photo favorite",
        ) from error
    return _photo_response(photo, service, authenticated_user.id)
