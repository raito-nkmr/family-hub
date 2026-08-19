from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.features.photos import trash_service as trash_service_module
from app.features.photos.access_service import PhotoAccessService
from app.features.photos.export_service import PhotoExportService
from app.features.photos.image_validation import ImageMetadata
from app.features.photos.metadata_service import PhotoMetadataService
from app.features.photos.models import (
    PhotoActivityEventType,
    PhotoDerivativeKind,
    PhotoLifecycleState,
    PhotoVisibility,
)
from app.features.photos.registration import register_staged_photo
from app.features.photos.service import (
    InvalidTrashCursorError,
    PhotoBulkSelectionError,
    PhotoContentUnavailableError,
    PhotoDeletePersistenceError,
    PhotoExportSelectionError,
    PhotoNotFoundError,
    PhotoUpdateConflictError,
    PhotoUpdateForbiddenError,
    PhotoUpdateStorageError,
)
from app.features.photos.storage import (
    OriginalNotFoundError,
    PhotoStorage,
    PhotoStorageError,
    StagedUpload,
)
from app.features.photos.trash_service import PhotoTrashService
from tests.features.photos.factories import make_photo


def make_access_service(session: Session) -> tuple[PhotoAccessService, MagicMock]:
    storage = MagicMock(spec=PhotoStorage)
    return PhotoAccessService(session, storage), storage


def make_export_service(session: Session) -> tuple[PhotoExportService, MagicMock]:
    storage = MagicMock(spec=PhotoStorage)
    return PhotoExportService(session, storage), storage


def make_metadata_service(session: Session) -> tuple[PhotoMetadataService, MagicMock]:
    storage = MagicMock(spec=PhotoStorage)
    return PhotoMetadataService(session, storage), storage


def make_trash_service(session: Session) -> tuple[PhotoTrashService, MagicMock]:
    storage = MagicMock(spec=PhotoStorage)
    return PhotoTrashService(session, storage), storage


def test_get_photo_returns_photo() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo

    service, _ = make_access_service(session)

    result = service.get_photo(photo.id, uuid4())

    assert result is photo
    session.scalar.assert_called_once()


def test_get_photo_raises_when_photo_does_not_exist() -> None:
    session = MagicMock(spec=Session)
    photo_id = uuid4()
    session.scalar.return_value = None
    service, _ = make_access_service(session)

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
    service, _ = make_trash_service(session)

    page = service.list_trashed_photos(first.uploaded_by_user_id, limit=1)

    assert page.items == [first]
    assert page.favorite_photo_ids == {first.id}
    assert page.total_count == 2
    assert page.next_cursor is not None
    statement = session.scalars.call_args_list[0].args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY photos.trashed_at DESC, photos.id DESC" in sql


def test_list_trashed_photos_rejects_invalid_cursor() -> None:
    service, _ = make_trash_service(MagicMock(spec=Session))

    with pytest.raises(InvalidTrashCursorError):
        service.list_trashed_photos(uuid4(), cursor="not-a-cursor")


def test_permanent_delete_logs_sidecar_restore_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    photo.lifecycle_state = PhotoLifecycleState.TRASHED
    photo.trashed_at = datetime(2026, 7, 15, 3, tzinfo=UTC)
    photo.trashed_by_user_id = photo.uploaded_by_user_id
    photo.purge_after = datetime(2026, 8, 14, 3, tzinfo=UTC)
    session.scalar.return_value = photo
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))
    service, storage = make_trash_service(session)
    storage.update_sidecar.side_effect = [None, PhotoStorageError("restore failed")]
    logger = MagicMock()
    monkeypatch.setattr(trash_service_module, "logger", logger)

    with pytest.raises(PhotoDeletePersistenceError):
        service.permanently_delete_photo(photo.id, photo.uploaded_by_user_id)

    logger.exception.assert_called_once_with(
        "Failed to restore photo sidecar after lifecycle rollback photo_id=%s",
        photo.id,
    )
    session.rollback.assert_called_once_with()


def test_set_favorite_uses_idempotent_postgresql_insert() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    user_id = uuid4()
    session.scalar.return_value = photo
    service, _ = make_access_service(session)

    result = service.set_favorite(photo.id, user_id, True)

    assert result is photo
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "INSERT INTO photo_favorites" in sql
    assert "ON CONFLICT (user_id, photo_id) DO NOTHING" in sql
    session.commit.assert_called_once_with()


def test_get_photo_content_returns_verified_path(tmp_path) -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo
    service, storage = make_access_service(session)
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
    service, storage = make_access_service(session)
    storage.get_original_path.side_effect = OriginalNotFoundError("missing")

    with pytest.raises(PhotoContentUnavailableError) as error:
        service.get_photo_content(photo.id, uuid4())

    assert error.value.photo_id == photo.id


def test_get_photo_export_entries_preserves_requested_order(tmp_path: Path) -> None:
    session = MagicMock(spec=Session)
    owner_id = uuid4()
    photos = [make_photo(uploaded_by_user_id=owner_id), make_photo(uploaded_by_user_id=owner_id)]
    session.scalars.return_value.all.return_value = list(reversed(photos))
    service, storage = make_export_service(session)
    storage.get_original_path.side_effect = lambda storage_key: tmp_path / Path(storage_key).name

    entries = service.get_photo_export_entries([photo.id for photo in photos], owner_id)

    assert [entry.photo_id for entry in entries] == [photo.id for photo in photos]
    assert [entry.original_filename for entry in entries] == [photo.original_filename for photo in photos]


def test_get_photo_export_entries_rejects_photos_not_owned_by_user() -> None:
    session = MagicMock(spec=Session)
    owner_id = uuid4()
    requested_ids = [uuid4(), uuid4()]
    session.scalars.return_value.all.return_value = [make_photo(requested_ids[0], uploaded_by_user_id=owner_id)]
    service, storage = make_export_service(session)

    with pytest.raises(PhotoExportSelectionError):
        service.get_photo_export_entries(requested_ids, owner_id)

    storage.get_original_path.assert_not_called()


def test_get_photo_thumbnail_returns_generated_derivative(tmp_path: Path) -> None:
    session = MagicMock(spec=Session)
    photo = make_photo()
    session.scalar.return_value = photo
    service, storage = make_access_service(session)
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
    service, storage = make_metadata_service(session)

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
    service, _ = make_metadata_service(session)

    service.update_photo(
        photo.id,
        photo.uploaded_by_user_id,
        photo.uploaded_by_username,
        memo=None,
        update_memo=False,
        sharing_group_ids={group_id},
        expected_version=1,
    )


def test_update_photo_preserves_share_from_group_the_owner_can_no_longer_see() -> None:
    session = MagicMock(spec=Session)
    hidden_group_id = uuid4()
    photo = make_photo(visibility=PhotoVisibility.SHARED, group_id=hidden_group_id)
    session.scalar.return_value = photo
    session.scalars.return_value.all.return_value = []
    service, storage = make_metadata_service(session)

    result = service.update_photo(
        photo.id,
        photo.uploaded_by_user_id,
        photo.uploaded_by_username,
        memo=None,
        update_memo=False,
        sharing_group_ids=set(),
        expected_version=1,
    )

    assert result.sharing["group_ids"] == [hidden_group_id]
    assert storage.update_sidecar.call_args.args[0].sharing_audiences == (
        {"type": "group", "id": str(hidden_group_id)},
    )

    session.add.assert_not_called()


def test_update_photo_removes_photo_from_albums_after_sharing_is_revoked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    photo = make_photo(visibility=PhotoVisibility.SHARED, group_id=group_id)
    session.scalar.return_value = photo
    session.scalars.return_value.all.return_value = [group_id]
    remove_from_albums = MagicMock()
    monkeypatch.setattr("app.features.photos.metadata_service.remove_photo_from_group_albums", remove_from_albums)
    service, _ = make_metadata_service(session)

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
    service, storage = make_metadata_service(session)

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
    service, storage = make_metadata_service(session)

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
    service, storage = make_metadata_service(session)

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
    service, storage = make_metadata_service(session)
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
    service, storage = make_metadata_service(session)
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
    service, storage = make_metadata_service(session)
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
    service, storage = make_metadata_service(session)

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
    service, storage = make_metadata_service(session)

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
    service, storage = make_metadata_service(session)

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


def configure_staged_upload(tmp_path: Path) -> StagedUpload:
    staged = StagedUpload(uuid4(), tmp_path / "photo.part", 5, "b" * 64)
    return staged


def test_register_staged_photo_does_not_change_database_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    storage = MagicMock(spec=PhotoStorage)
    staged = configure_staged_upload(tmp_path)
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
