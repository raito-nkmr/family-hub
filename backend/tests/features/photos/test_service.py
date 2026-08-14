from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.features.photos.image_validation import ImageMetadata
from app.features.photos.models import PhotoActivityEventType, PhotoDerivativeKind, PhotoVisibility
from app.features.photos.registration import DuplicatePhotoError, register_staged_photo
from app.features.photos.service import (
    InvalidTrashCursorError,
    PhotoBulkSelectionError,
    PhotoContentUnavailableError,
    PhotoExportSelectionError,
    PhotoNotFoundError,
    PhotoService,
    PhotoUpdateConflictError,
    PhotoUpdateForbiddenError,
    PhotoUpdateStorageError,
    PhotoUploadPersistenceError,
)
from app.features.photos.storage import (
    FinalizedUpload,
    OriginalNotFoundError,
    PhotoStorage,
    PhotoStorageError,
    StagedDerivative,
    StagedUpload,
)
from tests.features.photos.factories import make_photo


def make_service(session: Session) -> tuple[PhotoService, MagicMock]:
    storage = MagicMock(spec=PhotoStorage)
    return PhotoService(session, storage, "Asia/Tokyo"), storage


def test_get_photo_returns_photo() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo

    service, _ = make_service(session)

    result = service.get_photo(photo.id, uuid4())

    assert result is photo
    session.scalar.assert_called_once()


def test_get_photo_raises_when_photo_does_not_exist() -> None:
    session = MagicMock(spec=Session)
    photo_id = uuid4()
    session.scalar.return_value = None
    service, _ = make_service(session)

    with pytest.raises(PhotoNotFoundError) as error:
        service.get_photo(photo_id, uuid4())

    assert error.value.photo_id == photo_id


def test_list_trashed_photos_returns_bounded_page_and_favorites() -> None:
    session = MagicMock(spec=Session)
    first = make_photo()
    second = make_photo()
    for index, photo in enumerate((first, second)):
        photo.trashed_at = datetime(2026, 7, 15 - index, tzinfo=UTC)
    first_result = MagicMock()
    first_result.all.return_value = [first, second]
    favorite_result = MagicMock()
    favorite_result.all.return_value = [first.id]
    session.scalars.side_effect = [first_result, favorite_result]
    session.scalar.return_value = 2
    service, _ = make_service(session)

    page = service.list_trashed_photos(first.uploaded_by_user_id, limit=1)

    assert page.items == [first]
    assert page.favorite_photo_ids == {first.id}
    assert page.total_count == 2
    assert page.next_cursor is not None
    statement = session.scalars.call_args_list[0].args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY photos.trashed_at DESC, photos.id DESC" in sql


def test_list_trashed_photos_rejects_invalid_cursor() -> None:
    service, _ = make_service(MagicMock(spec=Session))

    with pytest.raises(InvalidTrashCursorError):
        service.list_trashed_photos(uuid4(), cursor="not-a-cursor")


def test_set_favorite_creates_user_specific_record() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    user_id = uuid4()
    session.scalar.return_value = photo
    session.get.return_value = None
    service, _ = make_service(session)

    result = service.set_favorite(photo.id, user_id, True)

    assert result is photo
    favorite = session.add.call_args.args[0]
    assert favorite.user_id == user_id
    assert favorite.photo_id == photo.id
    session.commit.assert_called_once_with()


def test_get_photo_content_returns_verified_path(tmp_path) -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo
    service, storage = make_service(session)
    original_path = tmp_path / "photo.jpg"
    storage.get_original_path.return_value = original_path

    result = service.get_photo_content(photo.id, uuid4())

    assert result.path == original_path
    assert result.content_type == photo.content_type
    storage.get_original_path.assert_called_once_with(photo.storage_key)


def test_get_photo_content_reports_storage_failure() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo
    service, storage = make_service(session)
    storage.get_original_path.side_effect = OriginalNotFoundError("missing")

    with pytest.raises(PhotoContentUnavailableError) as error:
        service.get_photo_content(photo.id, uuid4())

    assert error.value.photo_id == photo.id


def test_get_photo_export_entries_preserves_requested_order(tmp_path: Path) -> None:
    session = MagicMock(spec=Session)
    owner_id = uuid4()
    photos = [make_photo(uploaded_by_user_id=owner_id), make_photo(uploaded_by_user_id=owner_id)]
    session.scalars.return_value.all.return_value = list(reversed(photos))
    service, storage = make_service(session)
    storage.get_original_path.side_effect = lambda storage_key: tmp_path / Path(storage_key).name

    entries = service.get_photo_export_entries([photo.id for photo in photos], owner_id)

    assert [entry.photo_id for entry in entries] == [photo.id for photo in photos]
    assert [entry.original_filename for entry in entries] == [photo.original_filename for photo in photos]


def test_get_photo_export_entries_rejects_photos_not_owned_by_user() -> None:
    session = MagicMock(spec=Session)
    owner_id = uuid4()
    requested_ids = [uuid4(), uuid4()]
    session.scalars.return_value.all.return_value = [make_photo(requested_ids[0], uploaded_by_user_id=owner_id)]
    service, storage = make_service(session)

    with pytest.raises(PhotoExportSelectionError):
        service.get_photo_export_entries(requested_ids, owner_id)

    storage.get_original_path.assert_not_called()


def test_get_photo_thumbnail_returns_generated_derivative(tmp_path: Path) -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo
    service, storage = make_service(session)
    thumbnail_path = tmp_path / "thumbnail.webp"
    storage.get_derivative_path.return_value = thumbnail_path

    result = service.get_photo_thumbnail(photo.id, uuid4())

    derivative = photo.get_derivative(PhotoDerivativeKind.THUMBNAIL)
    assert derivative is not None
    assert result.path == thumbnail_path
    assert result.content_type == "image/webp"
    storage.get_derivative_path.assert_called_once_with(derivative.storage_key)


def test_update_photo_updates_memo_sharing_sidecar_and_database() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    group_id = uuid4()
    session.scalar.return_value = photo
    session.scalars.return_value.all.return_value = [group_id]
    service, storage = make_service(session)

    result = service.update_photo(
        photo.id,
        photo.uploaded_by_user_id,
        photo.uploaded_by_username,
        memo="北海道旅行",
        update_memo=True,
        sharing_group_ids={group_id},
        expected_version=1,
    )

    assert result.visibility is PhotoVisibility.SHARED
    assert result.memo == "北海道旅行"
    assert result.memo_updated_by_user_id == photo.uploaded_by_user_id
    assert result.memo_updated_by_username == photo.uploaded_by_username
    assert result.metadata_version == 2
    sidecar = storage.update_sidecar.call_args.args[0]
    assert sidecar.memo == "北海道旅行"
    assert sidecar.sharing_audiences == ({"type": "group", "id": str(group_id)},)
    event = session.add.call_args.args[0]
    assert event.event_type is PhotoActivityEventType.SHARED
    assert [group.group_id for group in event.groups] == [group_id]
    session.commit.assert_called_once_with()


def test_update_photo_does_not_repeat_activity_for_an_existing_share() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    photo = make_photo(visibility=PhotoVisibility.SHARED, group_id=group_id)
    session.scalar.return_value = photo
    session.scalars.return_value.all.return_value = [group_id]
    service, _ = make_service(session)

    service.update_photo(
        photo.id,
        photo.uploaded_by_user_id,
        photo.uploaded_by_username,
        memo=None,
        update_memo=False,
        sharing_group_ids={group_id},
        expected_version=1,
    )

    session.add.assert_not_called()


def test_update_photo_removes_photo_from_albums_after_sharing_is_revoked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    photo = make_photo(visibility=PhotoVisibility.SHARED, group_id=group_id)
    session.scalar.return_value = photo
    remove_from_albums = MagicMock()
    monkeypatch.setattr("app.features.photos.metadata_service.remove_photo_from_group_albums", remove_from_albums)
    service, _ = make_service(session)

    service.update_photo(
        photo.id,
        photo.uploaded_by_user_id,
        photo.uploaded_by_username,
        memo=None,
        update_memo=False,
        sharing_group_ids=set(),
        expected_version=1,
    )

    remove_from_albums.assert_called_once_with(session, photo.id, {group_id})


def test_bulk_add_sharing_updates_sidecars_and_groups_activity() -> None:
    session = MagicMock(spec=Session)
    owner_id = uuid4()
    group_id = uuid4()
    photos = [make_photo(uploaded_by_user_id=owner_id), make_photo(uploaded_by_user_id=owner_id)]
    session.scalars.return_value.all.side_effect = [[group_id], photos]
    service, storage = make_service(session)

    result = service.bulk_add_sharing(
        [photo.id for photo in photos],
        {group_id},
        owner_id,
        "owner",
    )

    assert result.updated_count == 2
    assert result.unchanged_count == 0
    assert storage.update_sidecar.call_count == 2
    assert all(photo.metadata_version == 2 for photo in photos)
    assert all(photo.sharing["group_ids"] == [group_id] for photo in photos)
    events = [call.args[0] for call in session.add.call_args_list]
    assert len(events) == 2
    assert {event.operation_id for event in events} == {result.operation_id}
    session.commit.assert_called_once_with()


def test_bulk_add_sharing_skips_existing_groups() -> None:
    session = MagicMock(spec=Session)
    owner_id = uuid4()
    group_id = uuid4()
    photo = make_photo(
        uploaded_by_user_id=owner_id,
        visibility=PhotoVisibility.SHARED,
        group_id=group_id,
    )
    session.scalars.return_value.all.side_effect = [[group_id], [photo]]
    service, storage = make_service(session)

    result = service.bulk_add_sharing([photo.id], {group_id}, owner_id, "owner")

    assert result.updated_count == 0
    assert result.unchanged_count == 1
    storage.update_sidecar.assert_not_called()
    session.add.assert_not_called()
    session.commit.assert_called_once_with()


def test_bulk_add_sharing_rejects_photos_not_owned_by_user() -> None:
    session = MagicMock(spec=Session)
    owner_id = uuid4()
    group_id = uuid4()
    requested_ids = [uuid4(), uuid4()]
    session.scalars.return_value.all.side_effect = [
        [group_id],
        [make_photo(requested_ids[0], uploaded_by_user_id=owner_id)],
    ]
    service, storage = make_service(session)

    with pytest.raises(PhotoBulkSelectionError):
        service.bulk_add_sharing(requested_ids, {group_id}, owner_id, "owner")

    session.rollback.assert_called_once_with()
    storage.update_sidecar.assert_not_called()


def test_bulk_add_sharing_restores_updated_sidecars_on_storage_failure() -> None:
    session = MagicMock(spec=Session)
    owner_id = uuid4()
    group_id = uuid4()
    photos = [make_photo(uploaded_by_user_id=owner_id), make_photo(uploaded_by_user_id=owner_id)]
    session.scalars.return_value.all.side_effect = [[group_id], photos]
    service, storage = make_service(session)
    update_count = 0

    def update_sidecar(metadata) -> None:
        nonlocal update_count
        update_count += 1
        if update_count == 2:
            raise PhotoStorageError("write failed")

    storage.update_sidecar.side_effect = update_sidecar

    with pytest.raises(PhotoUpdateStorageError):
        service.bulk_add_sharing([photo.id for photo in photos], {group_id}, owner_id, "owner")

    assert storage.update_sidecar.call_count == 3
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_update_photo_allows_viewer_to_update_shared_memo() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo
    service, storage = make_service(session)
    viewer_id = uuid4()

    result = service.update_photo(
        photo.id,
        viewer_id,
        "viewer",
        memo="共有メモ",
        update_memo=True,
        sharing_group_ids=None,
        expected_version=1,
    )

    assert result.memo == "共有メモ"
    assert result.memo_updated_by_user_id == viewer_id
    assert result.memo_updated_by_username == "viewer"
    storage.update_sidecar.assert_called_once()
    session.commit.assert_called_once()


def test_update_photo_allows_owner_to_override_capture_time() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo
    service, storage = make_service(session)
    override = datetime(2020, 1, 2, 3, tzinfo=UTC)

    result = service.update_photo(
        photo.id,
        photo.uploaded_by_user_id,
        photo.uploaded_by_username,
        memo=None,
        update_memo=False,
        sharing_group_ids=None,
        expected_version=1,
        captured_at_override=override,
        update_captured_at_override=True,
    )

    assert result.metadata_record.captured_at_override == override
    storage.update_sidecar.assert_called_once()
    session.commit.assert_called_once()


def test_update_photo_rejects_viewer_capture_time_override() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo
    service, storage = make_service(session)

    with pytest.raises(PhotoUpdateForbiddenError):
        service.update_photo(
            photo.id,
            uuid4(),
            "viewer",
            memo=None,
            update_memo=False,
            sharing_group_ids=None,
            expected_version=1,
            captured_at_override=datetime(2020, 1, 2, 3, tzinfo=UTC),
            update_captured_at_override=True,
        )

    storage.update_sidecar.assert_not_called()
    session.commit.assert_not_called()


def test_update_photo_rejects_non_owner_sharing_change() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo
    service, storage = make_service(session)

    with pytest.raises(PhotoUpdateForbiddenError):
        service.update_photo(
            photo.id,
            uuid4(),
            "viewer",
            memo=None,
            update_memo=False,
            sharing_group_ids={uuid4()},
            expected_version=1,
        )

    storage.update_sidecar.assert_not_called()
    session.commit.assert_not_called()


def test_update_photo_rejects_stale_metadata_version() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    photo.metadata_record.version = 2
    session.scalar.return_value = photo
    service, storage = make_service(session)

    with pytest.raises(PhotoUpdateConflictError):
        service.update_photo(
            photo.id,
            photo.uploaded_by_user_id,
            photo.uploaded_by_username,
            memo="stale",
            update_memo=True,
            sharing_group_ids=None,
            expected_version=1,
        )

    storage.update_sidecar.assert_not_called()


def configure_staged_upload(storage: MagicMock, tmp_path: Path) -> StagedUpload:
    staged = StagedUpload(uuid4(), tmp_path / "photo.part", 5, "b" * 64)
    thumbnail = StagedDerivative(
        path=tmp_path / "thumbnail.part",
        storage_key=f"thumbnails/2026/07/{staged.photo_id}.webp",
        content_type="image/webp",
        width=480,
        height=360,
        size_bytes=32_768,
    )
    storage.stage_upload.return_value = staged
    storage.stage_thumbnail.return_value = thumbnail
    storage.finalize_upload.return_value = FinalizedUpload(
        tmp_path / "photo.jpg", tmp_path / "photo.json", tmp_path / "thumbnail.webp"
    )
    return staged


def test_upload_photo_registers_finalized_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    service, storage = make_service(session)
    staged = configure_staged_upload(storage, tmp_path)
    captured_at = make_photo().captured_at
    monkeypatch.setattr(
        "app.features.photos.registration.inspect_image",
        lambda path, content_type, timezone: ImageMetadata("image/jpeg", ".jpg", 640, 480, captured_at),
    )

    uploader_id = uuid4()
    result = service.upload_photo(BytesIO(b"photo"), "original.jpg", "image/jpeg", uploader_id, "owner")

    assert result.original_filename == "original.jpg"
    assert result.uploaded_by_user_id == uploader_id
    assert result.uploaded_by_username == "owner"
    assert result.visibility is PhotoVisibility.PRIVATE
    assert result.storage_key == f"originals/{result.uploaded_at:%Y/%m}/{result.id}.jpg"
    assert result.sha256 == staged.sha256
    assert result.captured_at == captured_at
    session.add.assert_called_once_with(result)
    session.commit.assert_called_once_with()
    storage.finalize_upload.assert_called_once()
    thumbnail = storage.finalize_upload.call_args.args[1]
    sidecar = storage.finalize_upload.call_args.args[2]
    assert thumbnail is storage.stage_thumbnail.return_value
    assert sidecar.uploaded_by_user_id == uploader_id
    assert sidecar.uploaded_by_username == "owner"
    assert sidecar.memo is None
    assert sidecar.metadata_version == 1
    assert sidecar.sharing_audiences == ()
    assert sidecar.derivatives[0]["kind"] == PhotoDerivativeKind.THUMBNAIL
    storage.cleanup_staged.assert_called_once_with(staged)


def test_upload_photo_creates_activity_for_shared_groups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    session.scalar.return_value = None
    session.scalars.return_value.all.return_value = [group_id]
    service, storage = make_service(session)
    configure_staged_upload(storage, tmp_path)
    monkeypatch.setattr(
        "app.features.photos.registration.inspect_image",
        lambda path, content_type, timezone: ImageMetadata("image/jpeg", ".jpg", 640, 480, None),
    )

    photo = service.upload_photo(BytesIO(b"photo"), "original.jpg", "image/jpeg", uuid4(), "owner", {group_id})

    assert session.add.call_count == 2
    event = session.add.call_args_list[1].args[0]
    assert event.photo_id == photo.id
    assert event.event_type is PhotoActivityEventType.UPLOADED
    assert [group.group_id for group in event.groups] == [group_id]


def test_register_staged_photo_does_not_change_database_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    service, storage = make_service(session)
    staged = configure_staged_upload(storage, tmp_path)
    monkeypatch.setattr(
        "app.features.photos.registration.inspect_image",
        lambda path, content_type, timezone: ImageMetadata("image/jpeg", ".jpg", 640, 480, None),
    )

    registered = register_staged_photo(
        session,
        storage,
        "Asia/Tokyo",
        staged,
        "original.jpg",
        "image/jpeg",
        uuid4(),
        "owner",
    )

    assert registered.photo.id == staged.photo_id
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


def test_upload_photo_rejects_duplicate_before_finalizing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = uuid4()
    service, storage = make_service(session)
    staged = configure_staged_upload(storage, tmp_path)
    monkeypatch.setattr(
        "app.features.photos.registration.inspect_image",
        lambda path, content_type, timezone: ImageMetadata("image/jpeg", ".jpg", 640, 480, None),
    )

    uploader_id = uuid4()
    with pytest.raises(DuplicatePhotoError):
        service.upload_photo(BytesIO(b"photo"), "original.jpg", "image/jpeg", uploader_id, "owner")

    storage.finalize_upload.assert_not_called()
    storage.cleanup_staged.assert_called_once_with(staged)
    session.add.assert_not_called()
    session.rollback.assert_called_once_with()
    statement = session.scalar.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "photos.uploaded_by_user_id" in sql
    assert "photos.sha256" in sql


def test_upload_photo_removes_files_when_commit_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))
    service, storage = make_service(session)
    staged = configure_staged_upload(storage, tmp_path)
    finalized = storage.finalize_upload.return_value
    monkeypatch.setattr(
        "app.features.photos.registration.inspect_image",
        lambda path, content_type, timezone: ImageMetadata("image/jpeg", ".jpg", 640, 480, None),
    )

    with pytest.raises(PhotoUploadPersistenceError):
        service.upload_photo(BytesIO(b"photo"), "original.jpg", "image/jpeg", uuid4(), "owner")

    session.rollback.assert_called_once_with()
    storage.cleanup_finalized.assert_called_once_with(finalized)
    storage.cleanup_staged.assert_called_once_with(staged)
