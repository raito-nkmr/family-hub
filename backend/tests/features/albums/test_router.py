from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.albums.router import (
    add_album_photos,
    create_album,
    get_album,
    list_albums,
    remove_album_photo,
)
from app.features.albums.schemas import AlbumCreate, AlbumPhotoAdd
from app.features.albums.service import AlbumDetail, AlbumNotFoundError, AlbumSummary, PhotoNotFoundError
from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.main import create_app
from tests.features.photos.factories import make_photo

TEST_USER = AuthenticatedUser(id=uuid4(), username="owner")


def make_summary(photo_count: int = 0) -> AlbumSummary:
    now = datetime(2026, 7, 14, 3, tzinfo=UTC)
    return AlbumSummary(
        id=uuid4(),
        title="北海道旅行",
        description=None,
        created_by_user_id=TEST_USER.id,
        created_by_username=TEST_USER.username,
        group_id=uuid4(),
        group_name="同居家族",
        cover_photo_id=None,
        created_at=now,
        updated_at=now,
        photo_count=photo_count,
    )


class AlbumServiceStub:
    def __init__(self, detail: AlbumDetail | None = None, error: Exception | None = None) -> None:
        self.detail = detail
        self.error = error

    def _raise_error(self) -> None:
        if self.error is not None:
            raise self.error

    def list_albums(self, viewer_user_id: UUID) -> list[AlbumSummary]:
        self._raise_error()
        return [self.detail.album] if self.detail else []

    def get_album(self, album_id: UUID, viewer_user_id: UUID, **kwargs) -> AlbumDetail:
        self._raise_error()
        assert self.detail is not None
        return self.detail

    def create_album(self, **kwargs) -> AlbumSummary:
        self._raise_error()
        assert kwargs["created_by_user_id"] == TEST_USER.id
        assert self.detail is not None
        return self.detail.album

    def add_photos(self, album_id: UUID, photo_ids: list[UUID], acting_user_id: UUID) -> AlbumDetail:
        self._raise_error()
        assert photo_ids
        assert acting_user_id == TEST_USER.id
        assert self.detail is not None
        return self.detail

    def remove_photo(self, album_id: UUID, photo_id: UUID, acting_user_id: UUID) -> None:
        self._raise_error()


def test_list_albums_returns_items() -> None:
    detail = AlbumDetail(make_summary(), [])

    response = list_albums(TEST_USER, AlbumServiceStub(detail))

    assert response.items[0].id == detail.album.id


def test_create_album_returns_created_album() -> None:
    detail = AlbumDetail(make_summary(), [])

    response = create_album(
        AlbumCreate(title="北海道旅行", group_id=detail.album.group_id), TEST_USER, AlbumServiceStub(detail)
    )

    assert response.id == detail.album.id


def test_create_album_maps_unavailable_group_to_404() -> None:
    group_id = uuid4()

    with pytest.raises(HTTPException) as error:
        create_album(
            AlbumCreate(title="北海道旅行", group_id=group_id),
            TEST_USER,
            AlbumServiceStub(error=AlbumNotFoundError(group_id)),
        )

    assert error.value.status_code == 404


def test_get_album_returns_photos() -> None:
    photo = make_photo()
    detail = AlbumDetail(make_summary(photo_count=1), [photo], favorite_photo_ids={photo.id})

    response = get_album(detail.album.id, TEST_USER, AlbumServiceStub(detail))

    assert response.photos[0].id == photo.id
    assert response.photos[0].is_favorite is True
    assert response.next_cursor is None


def test_get_album_maps_missing_album_to_404() -> None:
    album_id = uuid4()

    with pytest.raises(HTTPException) as error:
        get_album(album_id, TEST_USER, AlbumServiceStub(error=AlbumNotFoundError(album_id)))

    assert error.value.status_code == 404
    assert error.value.detail == "Album not found"


def test_add_album_photos_maps_missing_photo_to_404() -> None:
    album_id = uuid4()
    photo_id = uuid4()

    with pytest.raises(HTTPException) as error:
        add_album_photos(
            album_id,
            AlbumPhotoAdd(photo_ids=[photo_id]),
            TEST_USER,
            AlbumServiceStub(error=PhotoNotFoundError({photo_id})),
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Photo not found"


def test_remove_album_photo_returns_no_content() -> None:
    response = remove_album_photo(uuid4(), uuid4(), TEST_USER, AlbumServiceStub())

    assert response.status_code == 204


def test_album_routes_are_in_openapi_schema() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert "get" in paths["/api/v1/albums"]
    assert "post" in paths["/api/v1/albums"]
    assert {"get", "patch", "delete"} <= set(paths["/api/v1/albums/{album_id}"])
    assert "post" in paths["/api/v1/albums/{album_id}/photos"]
    assert "delete" in paths["/api/v1/albums/{album_id}/photos/{photo_id}"]


def test_album_router_requires_authentication_and_mutations_require_csrf() -> None:
    from app.features.albums.router import router

    assert any(dependency.dependency is require_authenticated_user for dependency in router.dependencies)
    mutation_routes = [route for route in router.routes if route.methods & {"POST", "PATCH", "DELETE"}]
    assert mutation_routes
    assert all(
        any(dependency.dependency is require_csrf_token for dependency in route.dependencies)
        for route in mutation_routes
    )
