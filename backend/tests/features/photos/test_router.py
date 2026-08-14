from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, UploadFile
from httpx2 import ASGITransport, AsyncClient
from starlette.datastructures import Headers

from app.core.config import Settings
from app.core.middleware import SINGLE_PHOTO_MULTIPART_OVERHEAD_BYTES
from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.photos.activity import PhotoActivityItem, PhotoActivityPage
from app.features.photos.dependencies import get_photo_storage, get_photo_trash_service
from app.features.photos.models import Photo, PhotoActivityEventType, PhotoLifecycleState, PhotoVisibility
from app.features.photos.queries import PhotoListFilters, PhotoListItem, PhotoListPage, PhotoTimelineMonth
from app.features.photos.registration import (
    DuplicatePhotoError,
    InvalidPhotoError,
    PhotoUploadStorageError,
    UnsupportedPhotoTypeError,
)
from app.features.photos.router import (
    bulk_add_photo_sharing,
    download_photo_original,
    get_photo_content,
    get_photo_metadata,
    get_photo_thumbnail,
    get_photo_timeline,
    list_photo_activity,
    list_photo_metadata,
    mark_photo_activity_seen,
    update_photo_metadata,
    upload_photo,
)
from app.features.photos.schemas import (
    BulkPhotoSharingAdd,
    PhotoActivitySeenUpdate,
    PhotoListQuery,
    PhotoSharing,
    PhotoUpdate,
)
from app.features.photos.service import (
    BulkPhotoSharingResult,
    PhotoContent,
    PhotoContentUnavailableError,
    PhotoNotFoundError,
    PhotoTooLargeError,
    PhotoUpdateForbiddenError,
    TrashedPhotoPage,
)
from app.features.photos.storage import PhotoStorage, StorageStatus, StorageStatusCode
from app.main import create_app
from tests.features.photos.factories import make_photo


class AvailableStorage(PhotoStorage):
    def __init__(self) -> None:
        pass

    def get_status(self) -> StorageStatus:
        return StorageStatus(
            status=StorageStatusCode.AVAILABLE,
            writable=True,
            free_bytes=2_048,
            minimum_free_bytes=1_024,
        )


async def get_available_storage() -> AvailableStorage:
    return AvailableStorage()


TEST_USER = AuthenticatedUser(id=uuid4(), username="owner")


async def get_authenticated_user() -> AuthenticatedUser:
    return TEST_USER


@pytest.mark.anyio
async def test_get_storage_status_returns_storage_details() -> None:
    app = create_app(Settings(app_env="test"))
    app.dependency_overrides[get_photo_storage] = get_available_storage
    app.dependency_overrides[require_authenticated_user] = get_authenticated_user
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/photos/storage-status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "available",
        "available": True,
        "writable": True,
        "free_bytes": 2_048,
        "minimum_free_bytes": 1_024,
        "total_bytes": None,
    }


@pytest.mark.anyio
async def test_get_storage_status_uses_application_settings() -> None:
    app = create_app(Settings(app_env="test"))
    app.dependency_overrides[require_authenticated_user] = get_authenticated_user
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/photos/storage-status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "not_configured",
        "available": False,
        "writable": False,
        "free_bytes": None,
        "minimum_free_bytes": None,
        "total_bytes": None,
    }


@pytest.mark.anyio
async def test_list_trash_returns_paginated_response_without_favorite_n_plus_one() -> None:
    photo = make_photo(uploaded_by_user_id=TEST_USER.id)
    photo.lifecycle_state = PhotoLifecycleState.TRASHED
    photo.trashed_at = datetime(2026, 7, 15, tzinfo=UTC)
    photo.trashed_by_user_id = TEST_USER.id
    photo.purge_after = datetime(2026, 8, 14, tzinfo=UTC)
    service = PhotoServiceStub([photo, make_photo(uploaded_by_user_id=TEST_USER.id)])
    app = create_app(Settings(app_env="test"))
    app.dependency_overrides[require_authenticated_user] = get_authenticated_user
    app.dependency_overrides[get_photo_trash_service] = lambda: service
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/photos/trash?limit=1")

    assert response.status_code == 200
    assert response.json()["next_cursor"] == "next-page"
    assert response.json()["total_count"] == 2
    assert response.json()["items"][0]["is_favorite"] is True


@pytest.mark.anyio
async def test_single_photo_upload_rejects_oversized_request_before_authentication() -> None:
    app = create_app(Settings(app_env="test", photo_max_upload_bytes=5))
    transport = ASGITransport(app=app)

    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/photos",
            content=b"x",
            headers={"Content-Length": str(SINGLE_PHOTO_MULTIPART_OVERHEAD_BYTES + 6)},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Photo is too large"}


@pytest.mark.anyio
async def test_single_photo_upload_counts_streamed_body_without_content_length() -> None:
    app = create_app(Settings(app_env="test", photo_max_upload_bytes=5))
    transport = ASGITransport(app=app)

    async def oversized_body():
        yield b"x" * (SINGLE_PHOTO_MULTIPART_OVERHEAD_BYTES + 6)

    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/photos",
            content=oversized_body(),
            headers={"Content-Type": "multipart/form-data; boundary=test"},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Photo is too large"}


class PhotoServiceStub:
    def __init__(
        self,
        photos: list[Photo],
        content: PhotoContent | None = None,
        upload_error: Exception | None = None,
    ) -> None:
        self.photos = photos
        self.content = content
        self.upload_error = upload_error

    def list_photos(self, viewer_user_id: UUID, filters: PhotoListFilters) -> PhotoListPage:
        assert viewer_user_id == TEST_USER.id
        assert filters.limit == 50
        return PhotoListPage(
            items=[
                PhotoListItem(
                    id=photo.id,
                    uploaded_by_user_id=photo.uploaded_by_user_id,
                    uploaded_by_username=photo.uploaded_by_username,
                    visibility=photo.visibility,
                    original_filename=photo.original_filename,
                    content_type=photo.content_type,
                    width=photo.width,
                    height=photo.height,
                    captured_at=photo.captured_at,
                    uploaded_at=photo.uploaded_at,
                    is_favorite=False,
                )
                for photo in self.photos
            ],
            next_cursor=None,
            total_count=len(self.photos),
        )

    def list_trashed_photos(self, viewer_user_id: UUID, *, limit: int, cursor: str | None) -> TrashedPhotoPage:
        assert viewer_user_id == TEST_USER.id
        assert limit == 1
        assert cursor is None
        return TrashedPhotoPage(self.photos[:1], {self.photos[0].id}, "next-page", len(self.photos))

    def timeline(self, viewer_user_id: UUID, year: int) -> list[PhotoTimelineMonth]:
        assert viewer_user_id == TEST_USER.id
        assert year == 2026
        return [PhotoTimelineMonth(month="2026-07", count=len(self.photos))]

    def list_activity(self, viewer_user_id: UUID, *, limit: int, cursor: str | None) -> PhotoActivityPage:
        assert viewer_user_id == TEST_USER.id
        assert limit == 30
        assert cursor is None
        photo = self.photos[0]
        return PhotoActivityPage(
            items=[
                PhotoActivityItem(
                    id=uuid4(),
                    event_type=PhotoActivityEventType.UPLOADED,
                    actor_user_id=photo.uploaded_by_user_id,
                    actor_username=photo.uploaded_by_username,
                    operation_id=uuid4(),
                    occurred_at=photo.uploaded_at,
                    photo=PhotoListItem(
                        id=photo.id,
                        uploaded_by_user_id=photo.uploaded_by_user_id,
                        uploaded_by_username=photo.uploaded_by_username,
                        visibility=photo.visibility,
                        original_filename=photo.original_filename,
                        content_type=photo.content_type,
                        width=photo.width,
                        height=photo.height,
                        captured_at=photo.captured_at,
                        uploaded_at=photo.uploaded_at,
                        is_favorite=False,
                    ),
                )
            ],
            next_cursor=None,
            unseen_count=1,
        )

    def mark_seen(self, viewer_user_id: UUID, event_id: UUID) -> None:
        assert viewer_user_id == TEST_USER.id
        assert event_id

    def bulk_add_sharing(
        self,
        photo_ids: list[UUID],
        add_group_ids: set[UUID],
        acting_user_id: UUID,
        acting_username: str,
    ) -> BulkPhotoSharingResult:
        if self.upload_error is not None:
            raise self.upload_error
        assert acting_user_id == TEST_USER.id
        assert acting_username == TEST_USER.username
        return BulkPhotoSharingResult(
            operation_id=uuid4(),
            updated_count=len(photo_ids),
            unchanged_count=0,
        )

    def get_photo(self, photo_id: UUID, viewer_user_id: UUID) -> Photo:
        assert viewer_user_id == TEST_USER.id
        for photo in self.photos:
            if photo.id == photo_id:
                return photo
        raise PhotoNotFoundError(photo_id)

    def get_photo_content(self, photo_id: UUID, viewer_user_id: UUID) -> PhotoContent:
        self.get_photo(photo_id, viewer_user_id)
        if self.content is None:
            raise PhotoContentUnavailableError(photo_id)
        return self.content

    def get_photo_thumbnail(self, photo_id: UUID, viewer_user_id: UUID) -> PhotoContent:
        return self.get_photo_content(photo_id, viewer_user_id)

    def is_favorite(self, photo_id: UUID, user_id: UUID) -> bool:
        return False

    def update_photo(
        self,
        photo_id: UUID,
        acting_user_id: UUID,
        acting_username: str,
        *,
        memo: str | None,
        update_memo: bool,
        sharing_group_ids: set[UUID] | None,
        expected_version: int,
    ) -> Photo:
        if self.upload_error is not None:
            raise self.upload_error
        photo = self.get_photo(photo_id, acting_user_id)
        assert expected_version == photo.metadata_version
        if update_memo:
            photo.metadata_record.memo = memo
            photo.metadata_record.memo_updated_by_user_id = acting_user_id
            photo.metadata_record.memo_updated_by_username = acting_username
        if sharing_group_ids is not None:
            group_id = next(iter(sharing_group_ids), None)
            photo.shares = make_photo(
                visibility=PhotoVisibility.SHARED if group_id else PhotoVisibility.PRIVATE,
                group_id=group_id,
            ).shares
        photo.metadata_record.version += 1
        return photo

    def upload_photo(
        self,
        source,
        original_filename: str,
        declared_content_type: str | None,
        uploaded_by_user_id: UUID,
        uploaded_by_username: str,
        group_ids: set[UUID] | None = None,
    ) -> Photo:
        if self.upload_error is not None:
            raise self.upload_error
        assert uploaded_by_user_id == TEST_USER.id
        assert uploaded_by_username == TEST_USER.username
        return self.photos[0]


def test_list_photo_metadata_returns_items() -> None:
    photo = make_photo()

    response = list_photo_metadata(PhotoListQuery(), authenticated_user=TEST_USER, service=PhotoServiceStub([photo]))

    assert [item.id for item in response.items] == [photo.id]
    assert response.items[0].uploaded_at == datetime(2026, 7, 14, 4, tzinfo=UTC)
    assert response.next_cursor is None
    assert response.total_count == 1


def test_get_photo_timeline_returns_month_counts() -> None:
    response = get_photo_timeline(TEST_USER, PhotoServiceStub([make_photo()]), 2026)

    assert response.year == 2026
    assert response.months[0].month == "2026-07"
    assert response.months[0].count == 1


def test_list_photo_activity_returns_new_shared_photos() -> None:
    photo = make_photo(visibility=PhotoVisibility.SHARED)

    response = list_photo_activity(TEST_USER, PhotoServiceStub([photo]))

    assert response.unseen_count == 1
    assert response.items[0].photo.id == photo.id


def test_mark_photo_activity_seen_returns_no_content_body() -> None:
    event_id = uuid4()

    result = mark_photo_activity_seen(
        PhotoActivitySeenUpdate(event_id=event_id),
        TEST_USER,
        PhotoServiceStub([make_photo()]),
    )

    assert result is None


def test_bulk_add_photo_sharing_returns_updated_count() -> None:
    photo_ids = [uuid4(), uuid4()]
    group_id = uuid4()

    response = bulk_add_photo_sharing(
        BulkPhotoSharingAdd(photo_ids=photo_ids, add_group_ids=[group_id]),
        TEST_USER,
        PhotoServiceStub([]),
    )

    assert response.updated_count == 2
    assert response.unchanged_count == 0


def test_get_photo_metadata_returns_photo() -> None:
    photo = make_photo()

    response = get_photo_metadata(photo.id, authenticated_user=TEST_USER, service=PhotoServiceStub([photo]))

    assert response.id == photo.id


def test_get_photo_metadata_returns_404_when_missing() -> None:
    photo_id = uuid4()

    with pytest.raises(HTTPException) as error:
        get_photo_metadata(photo_id, authenticated_user=TEST_USER, service=PhotoServiceStub([]))

    assert error.value.status_code == 404
    assert error.value.detail == "Photo not found"


def test_get_photo_content_returns_file_response(tmp_path) -> None:
    photo = make_photo()
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"photo")
    service = PhotoServiceStub([photo], PhotoContent(path=path, content_type="image/jpeg"))

    response = get_photo_content(photo.id, authenticated_user=TEST_USER, service=service)

    assert response.path == path
    assert response.media_type == "image/jpeg"
    assert response.headers["cache-control"] == "private, no-store"


def test_download_photo_original_uses_attachment_filename(tmp_path) -> None:
    photo = make_photo()
    photo.original_filename = "北海道旅行.jpg"
    path = tmp_path / "stored.jpg"
    path.write_bytes(b"photo")
    service = PhotoServiceStub([photo], PhotoContent(path=path, content_type="image/jpeg"))

    response = download_photo_original(photo.id, authenticated_user=TEST_USER, service=service)

    assert response.path == path
    assert response.media_type == "image/jpeg"
    assert "attachment" in response.headers["content-disposition"]
    assert "filename*=utf-8''" in response.headers["content-disposition"].lower()
    assert response.headers["cache-control"] == "private, no-store"


def test_get_photo_content_returns_404_when_photo_is_missing() -> None:
    photo_id = uuid4()

    with pytest.raises(HTTPException) as error:
        get_photo_content(photo_id, authenticated_user=TEST_USER, service=PhotoServiceStub([]))

    assert error.value.status_code == 404
    assert error.value.detail == "Photo not found"


def test_get_photo_content_returns_503_when_original_is_unavailable() -> None:
    photo = make_photo()

    with pytest.raises(HTTPException) as error:
        get_photo_content(photo.id, authenticated_user=TEST_USER, service=PhotoServiceStub([photo]))

    assert error.value.status_code == 503
    assert error.value.detail == "Photo content unavailable"


def test_get_photo_thumbnail_returns_cacheable_file_response(tmp_path) -> None:
    photo = make_photo()
    path = tmp_path / "thumbnail.webp"
    path.write_bytes(b"thumbnail")
    service = PhotoServiceStub([photo], PhotoContent(path=path, content_type="image/webp"))

    response = get_photo_thumbnail(photo.id, authenticated_user=TEST_USER, service=service)

    assert response.path == path
    assert response.media_type == "image/webp"
    assert response.headers["cache-control"] == "private, no-store"


def make_upload_file() -> UploadFile:
    return UploadFile(
        BytesIO(b"photo"),
        filename="original.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )


def test_upload_photo_returns_created_metadata() -> None:
    photo = make_photo()

    service = PhotoServiceStub([photo])
    response = upload_photo(make_upload_file(), authenticated_user=TEST_USER, service=service, access_service=service)

    assert response.id == photo.id


@pytest.mark.parametrize(
    ("upload_error", "expected_status"),
    [
        (PhotoTooLargeError(), 413),
        (UnsupportedPhotoTypeError(), 415),
        (InvalidPhotoError(), 415),
        (DuplicatePhotoError(), 409),
        (PhotoUploadStorageError(StorageStatusCode.NOT_MOUNT_POINT), 503),
        (PhotoUploadStorageError(StorageStatusCode.INSUFFICIENT_SPACE), 507),
    ],
)
def test_upload_photo_maps_domain_errors(upload_error: Exception, expected_status: int) -> None:
    with pytest.raises(HTTPException) as error:
        upload_photo(
            make_upload_file(),
            authenticated_user=TEST_USER,
            service=(service := PhotoServiceStub([], upload_error=upload_error)),
            access_service=service,
        )

    assert error.value.status_code == expected_status


def test_photo_metadata_routes_are_in_openapi_schema() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert "get" in paths["/api/v1/photos"]
    assert "post" in paths["/api/v1/photos"]
    assert "get" in paths["/api/v1/photos/{photo_id}"]
    assert "patch" in paths["/api/v1/photos/{photo_id}"]
    assert "get" in paths["/api/v1/photos/{photo_id}/content"]
    assert "get" in paths["/api/v1/photos/{photo_id}/download"]
    assert "get" in paths["/api/v1/photos/{photo_id}/thumbnail"]
    assert "get" in paths["/api/v1/photos/activity"]
    assert "post" in paths["/api/v1/photos/activity/seen"]
    assert "post" in paths["/api/v1/photos/bulk-sharing"]
    assert "get" in paths["/api/v1/photos/export"]
    assert {"put", "delete"} <= set(paths["/api/v1/photos/{photo_id}/favorite"])


def test_update_photo_metadata_returns_updated_photo() -> None:
    photo = make_photo(uploaded_by_user_id=TEST_USER.id)
    group_id = uuid4()

    response = update_photo_metadata(
        photo.id,
        PhotoUpdate(
            memo="旅行のメモ",
            sharing=PhotoSharing(type=PhotoVisibility.SHARED, group_ids=[group_id]),
            version=1,
        ),
        TEST_USER,
        PhotoServiceStub([photo]),
        PhotoServiceStub([photo]),
    )

    assert response.visibility is PhotoVisibility.SHARED
    assert response.memo == "旅行のメモ"
    assert response.metadata_version == 2


def test_update_photo_metadata_rejects_non_owner_sharing_change() -> None:
    photo = make_photo()
    group_id = uuid4()

    with pytest.raises(HTTPException) as error:
        update_photo_metadata(
            photo.id,
            PhotoUpdate(sharing=PhotoSharing(type=PhotoVisibility.SHARED, group_ids=[group_id]), version=1),
            TEST_USER,
            PhotoServiceStub([photo], upload_error=PhotoUpdateForbiddenError()),
            PhotoServiceStub([photo], upload_error=PhotoUpdateForbiddenError()),
        )

    assert error.value.status_code == 403


def test_photo_router_requires_authentication_and_upload_requires_csrf() -> None:
    from app.features.photos.router import router

    assert any(dependency.dependency is require_authenticated_user for dependency in router.dependencies)
    application_routes = [route for route in router.routes if hasattr(route, "path")]
    upload_route = next(route for route in application_routes if route.path == "" and "POST" in route.methods)
    assert any(dependency.dependency is require_csrf_token for dependency in upload_route.dependencies)
    metadata_route = next(
        route for route in application_routes if route.path == "/{photo_id}" and "PATCH" in route.methods
    )
    assert any(dependency.dependency is require_csrf_token for dependency in metadata_route.dependencies)
