from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.features.albums.dependencies import get_album_service
from app.features.albums.schemas import (
    AlbumCreate,
    AlbumDetailResponse,
    AlbumListResponse,
    AlbumPhotoAdd,
    AlbumResponse,
    AlbumUpdate,
)
from app.features.albums.service import (
    AlbumDetail,
    AlbumNotFoundError,
    AlbumPersistenceError,
    AlbumService,
    InvalidAlbumPhotoCursorError,
    PhotoNotFoundError,
    PhotoNotInAlbumError,
)
from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
)
from app.features.photos.public import photo_response_from_model

router = APIRouter(
    tags=["albums"],
    dependencies=[Depends(require_authenticated_user), Depends(require_password_change_complete)],
)


def _detail_response(
    detail: AlbumDetail,
) -> AlbumDetailResponse:
    return AlbumDetailResponse(
        **AlbumResponse.model_validate(detail.album).model_dump(),
        photos=[
            photo_response_from_model(
                photo,
                visible_group_ids=detail.visible_group_ids.get(photo.id, set()),
                is_favorite=photo.id in detail.favorite_photo_ids,
            )
            for photo in detail.photos
        ],
        next_cursor=detail.next_cursor,
    )


def _raise_http_error(error: Exception) -> NoReturn:
    if isinstance(error, AlbumNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found") from error
    if isinstance(error, PhotoNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from error
    if isinstance(error, PhotoNotInAlbumError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo is not in album") from error
    if isinstance(error, AlbumPersistenceError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not persist album changes",
        ) from error
    raise error


@router.get("", response_model=AlbumListResponse)
def list_albums(
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AlbumService, Depends(get_album_service)],
) -> AlbumListResponse:
    return AlbumListResponse(
        items=[AlbumResponse.model_validate(album) for album in service.list_albums(authenticated_user.id)]
    )


@router.post(
    "",
    response_model=AlbumResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_album(
    body: AlbumCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AlbumService, Depends(get_album_service)],
) -> AlbumResponse:
    try:
        album = service.create_album(
            title=body.title,
            description=body.description,
            created_by_user_id=authenticated_user.id,
            created_by_username=authenticated_user.username,
            group_ids=body.group_ids,
        )
    except (AlbumNotFoundError, AlbumPersistenceError) as error:
        _raise_http_error(error)
    return AlbumResponse.model_validate(album)


@router.get("/{album_id}", response_model=AlbumDetailResponse)
def get_album(
    album_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AlbumService, Depends(get_album_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
) -> AlbumDetailResponse:
    try:
        return _detail_response(
            service.get_album(album_id, authenticated_user.id, limit=limit, cursor=cursor),
        )
    except AlbumNotFoundError as error:
        _raise_http_error(error)
    except InvalidAlbumPhotoCursorError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid album photo cursor") from error


@router.patch(
    "/{album_id}",
    response_model=AlbumResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_album(
    album_id: UUID,
    body: AlbumUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AlbumService, Depends(get_album_service)],
) -> AlbumResponse:
    try:
        album = service.update_album(
            album_id,
            title=body.title,
            description=body.description,
            update_description="description" in body.model_fields_set,
            acting_user_id=authenticated_user.id,
            cover_photo_id=body.cover_photo_id,
            update_cover="cover_photo_id" in body.model_fields_set,
            group_ids=body.group_ids,
            update_groups="group_ids" in body.model_fields_set,
            acting_username=authenticated_user.username,
        )
    except (AlbumNotFoundError, PhotoNotFoundError, PhotoNotInAlbumError, AlbumPersistenceError) as error:
        _raise_http_error(error)
    return AlbumResponse.model_validate(album)


@router.delete(
    "/{album_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def delete_album(
    album_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AlbumService, Depends(get_album_service)],
) -> Response:
    try:
        service.delete_album(album_id, authenticated_user.id)
    except (AlbumNotFoundError, AlbumPersistenceError) as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{album_id}/photos",
    response_model=AlbumDetailResponse,
    dependencies=[Depends(require_csrf_token)],
)
def add_album_photos(
    album_id: UUID,
    body: AlbumPhotoAdd,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AlbumService, Depends(get_album_service)],
) -> AlbumDetailResponse:
    try:
        return _detail_response(
            service.add_photos(album_id, body.photo_ids, authenticated_user.id, authenticated_user.username),
        )
    except (AlbumNotFoundError, PhotoNotFoundError, AlbumPersistenceError) as error:
        _raise_http_error(error)


@router.delete(
    "/{album_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def remove_album_photo(
    album_id: UUID,
    photo_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AlbumService, Depends(get_album_service)],
) -> Response:
    try:
        service.remove_photo(album_id, photo_id, authenticated_user.id)
    except (AlbumNotFoundError, PhotoNotInAlbumError, AlbumPersistenceError) as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
