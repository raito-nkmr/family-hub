from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.features.photos.models import (
    PhotoActivityEvent,
    PhotoVisibility,
    UploadBatch,
    UploadBatchGroupShare,
    UploadBatchStatus,
    UploadItem,
    UploadItemStatus,
)
from app.features.photos.registration import DuplicatePhotoError, RegisteredPhoto
from app.features.photos.schemas import UploadFileCreate
from app.features.photos.storage.facade import PhotoStorage
from app.features.photos.storage.types import FinalizedUpload, StorageStatusCode, StorageUnavailableError
from app.features.photos.uploads import (
    DUPLICATE_PHOTO_CONSTRAINT,
    UPLOAD_CAPACITY_LOCK_ID,
    UploadBatchInvalidError,
    UploadBatchPersistenceError,
    UploadBatchService,
    UploadBatchStorageError,
)


class IntegrityDiagnostic:
    def __init__(self, constraint_name: str) -> None:
        self.constraint_name = constraint_name


class IntegrityOrigin:
    def __init__(self, constraint_name: str) -> None:
        self.diag = IntegrityDiagnostic(constraint_name)


def make_service() -> tuple[UploadBatchService, MagicMock, MagicMock]:
    session = MagicMock(spec=Session)
    storage = MagicMock(spec=PhotoStorage)
    storage.maximum_upload_bytes = 1_024
    return UploadBatchService(session, storage, "Asia/Tokyo"), session, storage


def make_batch_and_item(*, expires_at: datetime | None = None) -> tuple[UploadBatch, UploadItem]:
    now = datetime.now(UTC)
    batch = UploadBatch(
        id=uuid4(),
        owner_user_id=uuid4(),
        status=UploadBatchStatus.ACTIVE,
        created_at=now,
        expires_at=expires_at or now + timedelta(hours=1),
        completed_at=None,
    )
    item = UploadItem(
        id=uuid4(),
        batch_id=batch.id,
        client_id="client-photo",
        original_filename="photo.jpg",
        declared_content_type="image/jpeg",
        size_bytes=5,
        received_bytes=0,
        status=UploadItemStatus.QUEUED,
        error_code=None,
        photo_id=None,
        created_at=now,
        completed_at=None,
    )
    return batch, item


def test_create_batch_reserves_capacity_and_creates_one_item_per_file() -> None:
    service, session, storage = make_service()
    owner_id = uuid4()
    group_id = uuid4()
    session.scalars.return_value.all.side_effect = [[group_id], [group_id], []]
    session.scalar.return_value = 7
    files = [
        UploadFileCreate(
            client_id="first",
            original_filename="first.jpg",
            declared_content_type="image/jpeg",
            size_bytes=5,
        ),
        UploadFileCreate(
            client_id="second",
            original_filename="second.png",
            declared_content_type="image/png",
            size_bytes=6,
        ),
    ]

    batch, items = service.create_batch(owner_id, files, {group_id})

    assert batch.status is UploadBatchStatus.ACTIVE
    assert batch.visibility is PhotoVisibility.SHARED
    assert batch.group_ids == [group_id]
    assert [item.client_id for item in items] == ["first", "second"]
    storage.require_capacity.assert_called_once_with(18)
    advisory_lock_statement = session.execute.call_args_list[0].args[0]
    assert str(advisory_lock_statement.compile(compile_kwargs={"literal_binds": True})) == (
        f"SELECT pg_advisory_xact_lock({UPLOAD_CAPACITY_LOCK_ID}) AS pg_advisory_xact_lock_1"
    )
    session.add_all.assert_called_once_with([batch, *items])
    session.commit.assert_called_once_with()


def test_create_batch_rejects_duplicate_client_identifiers() -> None:
    service, session, storage = make_service()
    files = [
        UploadFileCreate(
            client_id="same",
            original_filename="first.jpg",
            declared_content_type="image/jpeg",
            size_bytes=5,
        ),
        UploadFileCreate(
            client_id="same",
            original_filename="second.jpg",
            declared_content_type="image/jpeg",
            size_bytes=5,
        ),
    ]

    with pytest.raises(UploadBatchInvalidError):
        service.create_batch(uuid4(), files)

    storage.require_capacity.assert_not_called()
    session.add_all.assert_not_called()


def test_create_batch_preserves_insufficient_storage_status() -> None:
    service, session, storage = make_service()
    session.scalars.return_value.all.return_value = []
    session.scalar.return_value = 0
    storage.require_capacity.side_effect = StorageUnavailableError(StorageStatusCode.INSUFFICIENT_SPACE)
    files = [
        UploadFileCreate(
            client_id="first",
            original_filename="first.jpg",
            declared_content_type="image/jpeg",
            size_bytes=5,
        )
    ]

    with pytest.raises(UploadBatchStorageError) as caught:
        service.create_batch(uuid4(), files)

    assert caught.value.storage_status is StorageStatusCode.INSUFFICIENT_SPACE
    session.add_all.assert_not_called()


def test_append_chunk_persists_the_resumable_offset() -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    session.execute.return_value.one_or_none.return_value = (batch, item)
    storage.append_resumable_chunk.return_value = 3

    result = service.append_chunk(item.id, batch.owner_user_id, 0, b"pho")

    assert result == 3
    assert item.received_bytes == 3
    assert item.status is UploadItemStatus.UPLOADING
    storage.append_resumable_chunk.assert_called_once_with(item.id, 0, b"pho", 5)
    session.commit.assert_called_once_with()


def test_complete_item_marks_duplicates_without_failing_the_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    group_id = uuid4()
    batch.group_shares = [UploadBatchGroupShare(batch_id=batch.id, group_id=group_id)]
    item.received_bytes = item.size_bytes
    session.execute.return_value.one_or_none.return_value = (batch, item)
    session.scalars.return_value.all.return_value = [group_id]
    session.get.return_value = None
    session.scalar.return_value = 0
    storage.get_resumable_offset.return_value = item.size_bytes
    staged = MagicMock()
    storage.resumable_as_staged.return_value = staged
    register = MagicMock(side_effect=DuplicatePhotoError)
    monkeypatch.setattr("app.features.photos.uploads.register_staged_photo", register)

    result = service.complete_item(item.id, batch.owner_user_id, "owner")

    assert result.status is UploadItemStatus.DUPLICATE
    assert result.error_code == "duplicate"
    assert batch.status is UploadBatchStatus.COMPLETED
    storage.cleanup_resumable.assert_called_once_with(item.id)
    register.assert_called_once_with(
        session,
        storage,
        "Asia/Tokyo",
        staged,
        item.original_filename,
        item.declared_content_type,
        batch.owner_user_id,
        "owner",
        group_ids={group_id},
        activity_operation_id=batch.id,
    )
    membership_statement = str(session.scalars.call_args_list[0].args[0])
    assert "ORDER BY family_groups.id FOR UPDATE" in membership_statement
    session.commit.assert_called_once_with()


def test_complete_item_enqueues_one_notification_for_the_upload_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    group_id = uuid4()
    batch.group_shares = [UploadBatchGroupShare(batch_id=batch.id, group_id=group_id)]
    item.received_bytes = item.size_bytes
    session.execute.return_value.one_or_none.return_value = (batch, item)
    session.scalars.return_value.all.return_value = [group_id]
    session.get.return_value = None
    session.scalar.side_effect = [None, 0]
    storage.get_resumable_offset.return_value = item.size_bytes
    storage.resumable_as_staged.return_value = MagicMock()
    photo = MagicMock()
    photo.id = item.id
    activity = MagicMock(spec=PhotoActivityEvent)
    activity.activity_operation_id = batch.id
    finalized = MagicMock(spec=FinalizedUpload)
    monkeypatch.setattr(
        "app.features.photos.uploads.register_staged_photo",
        MagicMock(return_value=RegisteredPhoto(photo=photo, finalized_upload=finalized, activity_event=activity)),
    )
    enqueue = MagicMock()
    monkeypatch.setattr("app.features.photos.uploads.enqueue_group_notification", enqueue)

    result = service.complete_item(item.id, batch.owner_user_id, "owner")

    assert result.status is UploadItemStatus.SUCCEEDED
    enqueue.assert_called_once()
    assert enqueue.call_args.args[1:4] == ({group_id}, "photo_shared", f"photo:{batch.id}")
    assert enqueue.call_args.kwargs == {"exclude_user_id": batch.owner_user_id}


def test_complete_item_cancels_batch_when_group_access_was_revoked() -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    group_id = uuid4()
    batch.group_shares = [UploadBatchGroupShare(batch_id=batch.id, group_id=group_id)]
    session.execute.return_value.one_or_none.return_value = (batch, item)
    session.scalars.return_value.all.side_effect = [[], [item]]

    with pytest.raises(UploadBatchInvalidError, match="access was revoked"):
        service.complete_item(item.id, batch.owner_user_id, "owner")

    assert batch.status is UploadBatchStatus.CANCELED
    assert item.status is UploadItemStatus.FAILED
    assert item.error_code == "sharing_access_revoked"
    storage.cleanup_resumable.assert_called_once_with(item.id)
    session.commit.assert_called_once_with()


def test_complete_item_cleans_finalized_photo_when_batch_commit_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    item.received_bytes = item.size_bytes
    session.execute.return_value.one_or_none.return_value = (batch, item)
    session.get.return_value = None
    session.scalar.return_value = 0
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))
    storage.get_resumable_offset.return_value = item.size_bytes
    storage.resumable_as_staged.return_value = MagicMock()
    photo = MagicMock()
    photo.id = item.id
    finalized = MagicMock(spec=FinalizedUpload)
    monkeypatch.setattr(
        "app.features.photos.uploads.register_staged_photo",
        MagicMock(return_value=RegisteredPhoto(photo=photo, finalized_upload=finalized)),
    )

    with pytest.raises(UploadBatchPersistenceError):
        service.complete_item(item.id, batch.owner_user_id, "owner")

    storage.cleanup_finalized.assert_called_once_with(finalized)


def test_complete_item_treats_concurrent_photo_as_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    item.received_bytes = item.size_bytes
    session.execute.return_value.one_or_none.return_value = (batch, item)
    session.get.return_value = None
    session.scalar.return_value = 0
    session.flush.side_effect = IntegrityError("insert", {}, IntegrityOrigin(DUPLICATE_PHOTO_CONSTRAINT))
    storage.get_resumable_offset.return_value = item.size_bytes
    storage.resumable_as_staged.return_value = MagicMock()
    photo = MagicMock()
    photo.id = item.id
    finalized = MagicMock(spec=FinalizedUpload)
    monkeypatch.setattr(
        "app.features.photos.uploads.register_staged_photo",
        MagicMock(return_value=RegisteredPhoto(photo=photo, finalized_upload=finalized)),
    )

    result = service.complete_item(item.id, batch.owner_user_id, "owner")

    assert result.status is UploadItemStatus.DUPLICATE
    session.rollback.assert_called_once_with()
    storage.cleanup_finalized.assert_called_once_with(finalized)
    storage.cleanup_resumable.assert_called_once_with(item.id)


def test_complete_item_treats_an_unrelated_integrity_error_as_persistence_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    item.received_bytes = item.size_bytes
    session.execute.return_value.one_or_none.return_value = (batch, item)
    session.get.return_value = None
    session.scalar.return_value = 0
    session.flush.side_effect = IntegrityError("insert", {}, IntegrityOrigin("some_other_constraint"))
    storage.get_resumable_offset.return_value = item.size_bytes
    storage.resumable_as_staged.return_value = MagicMock()
    finalized = MagicMock(spec=FinalizedUpload)
    monkeypatch.setattr(
        "app.features.photos.uploads.register_staged_photo",
        MagicMock(return_value=RegisteredPhoto(photo=MagicMock(id=item.id), finalized_upload=finalized)),
    )

    with pytest.raises(UploadBatchPersistenceError):
        service.complete_item(item.id, batch.owner_user_id, "owner")

    session.rollback.assert_called_once_with()
    storage.cleanup_finalized.assert_called_once_with(finalized)
    storage.cleanup_resumable.assert_not_called()


def test_get_offset_rejects_terminal_item_without_changing_progress() -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    item.received_bytes = item.size_bytes
    item.status = UploadItemStatus.SUCCEEDED
    session.execute.return_value.one_or_none.return_value = (batch, item)

    with pytest.raises(UploadBatchInvalidError):
        service.get_offset(item.id, batch.owner_user_id)

    assert item.received_bytes == item.size_bytes
    storage.get_resumable_offset.assert_not_called()
    session.commit.assert_not_called()


def test_cancel_batch_locks_batch_and_items_before_changing_status() -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    item.status = UploadItemStatus.PROCESSING
    session.scalar.return_value = batch
    session.scalars.return_value.all.return_value = [item]

    service.cancel_batch(batch.id, batch.owner_user_id)

    batch_statement = session.scalar.call_args.args[0]
    items_statement = session.scalars.call_args.args[0]
    assert "FOR UPDATE" in str(batch_statement)
    assert "FOR UPDATE" in str(items_statement)
    assert batch.status is UploadBatchStatus.CANCELED
    assert item.status is UploadItemStatus.FAILED
    storage.cleanup_resumable.assert_called_once_with(item.id)
    session.commit.assert_called_once_with()


def test_cancel_batch_keeps_resumable_file_when_commit_fails() -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item()
    item.status = UploadItemStatus.PROCESSING
    session.scalar.return_value = batch
    session.scalars.return_value.all.return_value = [item]
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))

    with pytest.raises(UploadBatchPersistenceError):
        service.cancel_batch(batch.id, batch.owner_user_id)

    storage.cleanup_resumable.assert_not_called()
    session.rollback.assert_called_once_with()


def test_expire_stale_batches_locks_batches_and_items_before_cleanup() -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    item.status = UploadItemStatus.UPLOADING
    session.scalars.return_value.all.side_effect = [[batch], [item]]

    cleanup_ids = service._expire_stale_batches(commit=False)

    batch_statement = session.scalars.call_args_list[0].args[0]
    items_statement = session.scalars.call_args_list[1].args[0]
    assert "FOR UPDATE" in str(batch_statement)
    assert "FOR UPDATE" in str(items_statement)
    assert cleanup_ids == [item.id]
    storage.cleanup_resumable.assert_not_called()
    assert batch.status is UploadBatchStatus.CANCELED
    assert item.status is UploadItemStatus.FAILED


def test_expire_batch_keeps_resumable_file_when_commit_fails() -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    item.status = UploadItemStatus.UPLOADING
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))

    with pytest.raises(UploadBatchPersistenceError):
        service._expire_batch(batch, [item])

    storage.cleanup_resumable.assert_not_called()
    session.rollback.assert_called_once_with()


def test_expired_item_path_locks_all_items_before_cleanup() -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    item.status = UploadItemStatus.UPLOADING
    session.execute.return_value.one_or_none.return_value = (batch, item)
    session.scalars.return_value.all.return_value = [item]

    with pytest.raises(UploadBatchInvalidError, match="no longer active"):
        service.append_chunk(item.id, batch.owner_user_id, 0, b"pho")

    item_statement = session.scalars.call_args.args[0]
    assert "FOR UPDATE" in str(item_statement)
    storage.cleanup_resumable.assert_called_once_with(item.id)


def test_get_batch_expires_and_cleans_up_partial_items() -> None:
    service, session, storage = make_service()
    batch, item = make_batch_and_item(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    item.status = UploadItemStatus.UPLOADING
    session.scalar.return_value = batch
    session.scalars.return_value.all.return_value = [item]

    result_batch, result_items = service.get_batch(batch.id, batch.owner_user_id)

    assert result_batch.status is UploadBatchStatus.CANCELED
    assert result_items[0].status is UploadItemStatus.FAILED
    assert result_items[0].error_code == "expired"
    storage.cleanup_resumable.assert_called_once_with(item.id)
    session.commit.assert_called_once_with()
    assert any("FOR UPDATE" in str(call.args[0]) for call in session.scalar.call_args_list)
