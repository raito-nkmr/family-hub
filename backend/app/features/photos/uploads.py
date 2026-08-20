from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.groups.public import lock_user_group_ids
from app.features.notifications.public import NotificationType, enqueue_group_notification
from app.features.photos.models import (
    Photo,
    UploadBatch,
    UploadBatchGroupShare,
    UploadBatchStatus,
    UploadItem,
    UploadItemStatus,
)
from app.features.photos.registration import (
    ALLOWED_CONTENT_TYPES,
    DuplicatePhotoError,
    InvalidPhotoError,
    PhotoUploadStorageError,
    UnsupportedPhotoTypeError,
    register_staged_photo,
)
from app.features.photos.schemas import UploadFileCreate
from app.features.photos.storage import (
    PhotoStorage,
    PhotoStorageError,
    StorageStatusCode,
    StorageUnavailableError,
    UploadOffsetMismatchError,
    UploadTooLargeError,
)

UPLOAD_BATCH_TTL = timedelta(hours=24)
MAX_UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024
# Serialize storage-capacity reservations across application processes.  The value
# only needs to be stable and unique within this application's PostgreSQL database.
UPLOAD_CAPACITY_LOCK_ID = 0x70686F746F5F7570
TERMINAL_ITEM_STATUSES = {
    UploadItemStatus.SUCCEEDED,
    UploadItemStatus.DUPLICATE,
    UploadItemStatus.FAILED,
}
DUPLICATE_PHOTO_CONSTRAINT = "uq_photos_uploaded_by_user_id_sha256"


class UploadBatchNotFoundError(Exception):
    pass


class UploadItemNotFoundError(Exception):
    pass


class UploadBatchInvalidError(Exception):
    pass


class UploadChunkTooLargeError(Exception):
    pass


class UploadOffsetError(Exception):
    def __init__(self, actual_offset: int) -> None:
        self.actual_offset = actual_offset


class UploadBatchStorageError(Exception):
    def __init__(self, storage_status: StorageStatusCode | None = None) -> None:
        super().__init__("Photo storage is unavailable")
        self.storage_status = storage_status


class UploadBatchPersistenceError(Exception):
    pass


class UploadBatchService:
    def __init__(self, session: Session, storage: PhotoStorage, default_timezone: str) -> None:
        self._session = session
        self._storage = storage
        self._default_timezone = default_timezone

    def create_batch(
        self,
        owner_user_id: UUID,
        files: list[UploadFileCreate],
        group_ids: set[UUID] | None = None,
    ) -> tuple[UploadBatch, list[UploadItem]]:
        if len({file.client_id for file in files}) != len(files):
            raise UploadBatchInvalidError("Client file identifiers must be unique")
        resolved_group_ids = group_ids or set()
        if lock_user_group_ids(self._session, owner_user_id, resolved_group_ids) != resolved_group_ids:
            raise UploadBatchInvalidError("One or more sharing groups are unavailable")
        maximum = self._storage.maximum_upload_bytes
        if maximum is None or any(
            file.content_type not in ALLOWED_CONTENT_TYPES or file.size_bytes > maximum for file in files
        ):
            raise UploadBatchInvalidError("A file is unsupported or exceeds the size limit")

        self._session.execute(select(func.pg_advisory_xact_lock(UPLOAD_CAPACITY_LOCK_ID)))
        self._expire_stale_batches(commit=False)
        reserved = self._session.scalar(
            select(func.coalesce(func.sum(UploadItem.size_bytes - UploadItem.received_bytes), 0))
            .join(UploadBatch, UploadBatch.id == UploadItem.batch_id)
            .where(UploadBatch.status == UploadBatchStatus.ACTIVE)
        )
        try:
            self._storage.require_capacity(int(reserved or 0) + sum(file.size_bytes for file in files))
        except StorageUnavailableError as error:
            raise UploadBatchStorageError(error.status) from error

        now = datetime.now(UTC)
        batch_id = uuid4()
        batch = UploadBatch(
            id=batch_id,
            owner_user_id=owner_user_id,
            status=UploadBatchStatus.ACTIVE,
            created_at=now,
            expires_at=now + UPLOAD_BATCH_TTL,
            completed_at=None,
            group_shares=[
                UploadBatchGroupShare(batch_id=batch_id, group_id=group_id)
                for group_id in sorted(resolved_group_ids, key=str)
            ],
        )
        items = [
            UploadItem(
                id=uuid4(),
                batch_id=batch.id,
                client_id=file.client_id,
                original_filename=file.filename,
                declared_content_type=file.content_type,
                size_bytes=file.size_bytes,
                received_bytes=0,
                status=UploadItemStatus.QUEUED,
                error_code=None,
                photo_id=None,
                created_at=now,
                completed_at=None,
            )
            for file in files
        ]
        self._session.add_all([batch, *items])
        self._commit()
        return batch, items

    def get_batch(
        self,
        batch_id: UUID,
        owner_user_id: UUID,
        *,
        lock: bool = False,
    ) -> tuple[UploadBatch, list[UploadItem]]:
        batch_statement = select(UploadBatch).where(
            UploadBatch.id == batch_id,
            UploadBatch.owner_user_id == owner_user_id,
        )
        if lock:
            batch_statement = batch_statement.with_for_update()
        batch = self._session.scalar(batch_statement)
        if batch is None:
            raise UploadBatchNotFoundError
        items_statement = (
            select(UploadItem).where(UploadItem.batch_id == batch.id).order_by(UploadItem.created_at, UploadItem.id)
        )
        if lock:
            items_statement = items_statement.with_for_update()
        items = list(self._session.scalars(items_statement).all())
        if batch.status == UploadBatchStatus.ACTIVE and batch.expires_at <= datetime.now(UTC):
            batch = self._session.scalar(
                select(UploadBatch)
                .where(UploadBatch.id == batch.id, UploadBatch.owner_user_id == owner_user_id)
                .with_for_update()
            )
            if batch is None:
                raise UploadBatchNotFoundError
            items = list(
                self._session.scalars(
                    select(UploadItem)
                    .where(UploadItem.batch_id == batch.id)
                    .order_by(UploadItem.created_at, UploadItem.id)
                    .with_for_update()
                ).all()
            )
            self._expire_batch(batch, items)
        return batch, items

    def get_offset(self, item_id: UUID, owner_user_id: UUID) -> int:
        batch, item = self._get_item(item_id, owner_user_id, lock=True)
        self._require_active(batch, item)
        try:
            actual = self._storage.get_resumable_offset(item.id)
        except PhotoStorageError as error:
            raise UploadBatchStorageError(_storage_status(error)) from error
        if item.received_bytes != actual:
            item.received_bytes = actual
            self._commit()
        return actual

    def append_chunk(self, item_id: UUID, owner_user_id: UUID, offset: int, data: bytes) -> int:
        if len(data) > MAX_UPLOAD_CHUNK_BYTES:
            raise UploadChunkTooLargeError
        batch, item = self._get_item(item_id, owner_user_id, lock=True)
        self._require_active(batch, item)
        try:
            next_offset = self._storage.append_resumable_chunk(item.id, offset, data, item.size_bytes)
        except UploadOffsetMismatchError as error:
            item.received_bytes = error.actual_offset
            self._commit()
            raise UploadOffsetError(error.actual_offset) from error
        except (UploadTooLargeError, PhotoStorageError) as error:
            raise UploadBatchStorageError(_storage_status(error)) from error
        item.received_bytes = next_offset
        item.status = UploadItemStatus.UPLOADING
        self._commit()
        return next_offset

    def complete_item(self, item_id: UUID, owner_user_id: UUID, owner_username: str) -> UploadItem:
        batch, item = self._get_item(item_id, owner_user_id, lock=True)
        self._require_active(batch, item)
        sharing_group_ids = set(batch.group_ids)
        if lock_user_group_ids(self._session, owner_user_id, sharing_group_ids) != sharing_group_ids:
            self._cancel_batch_after_access_revocation(batch)
            raise UploadBatchInvalidError("Upload sharing access was revoked")
        existing_photo = self._session.get(Photo, item.id)
        if existing_photo is not None:
            return self._finish_item(batch, item, UploadItemStatus.SUCCEEDED, photo_id=existing_photo.id)
        try:
            actual = self._storage.get_resumable_offset(item.id)
        except PhotoStorageError as error:
            raise UploadBatchStorageError(_storage_status(error)) from error
        if actual != item.size_bytes:
            raise UploadOffsetError(actual)
        item.received_bytes = actual
        item.status = UploadItemStatus.PROCESSING
        try:
            staged = self._storage.resumable_as_staged(item.id, item.size_bytes)
            registered = register_staged_photo(
                self._session,
                self._storage,
                self._default_timezone,
                staged,
                item.original_filename,
                item.declared_content_type,
                owner_user_id,
                owner_username,
                group_ids=sharing_group_ids,
                activity_operation_id=batch.id,
            )
        except DuplicatePhotoError:
            self._storage.cleanup_resumable(item.id)
            return self._finish_item(batch, item, UploadItemStatus.DUPLICATE, error_code="duplicate")
        except (UnsupportedPhotoTypeError, InvalidPhotoError):
            self._storage.cleanup_resumable(item.id)
            return self._finish_item(batch, item, UploadItemStatus.FAILED, error_code="invalid_photo")
        except (PhotoUploadStorageError, PhotoStorageError) as error:
            try:
                actual = self._storage.get_resumable_offset(item.id)
            except PhotoStorageError:
                actual = 0
                self._storage.cleanup_resumable(item.id)
            item.received_bytes = actual
            item.status = UploadItemStatus.UPLOADING if actual else UploadItemStatus.QUEUED
            item.error_code = None
            self._commit()
            raise UploadBatchStorageError(_storage_status(error)) from error

        self._session.add(registered.photo)
        if registered.activity_event is not None:
            self._session.add(registered.activity_event)
            enqueue_group_notification(
                self._session,
                sharing_group_ids,
                NotificationType.PHOTO_SHARED,
                f"photo:{registered.activity_event.operation_id}",
                {
                    "url": "/photos/new",
                    "operation_id": str(registered.activity_event.operation_id),
                },
                exclude_user_id=owner_user_id,
            )
        try:
            self._session.flush()
        except IntegrityError as error:
            self._session.rollback()
            self._storage.cleanup_finalized(registered.finalized_upload)
            self._storage.cleanup_resumable(item.id)
            if _is_duplicate_photo_integrity_error(error):
                return self._finish_item(batch, item, UploadItemStatus.DUPLICATE, error_code="duplicate")
            raise UploadBatchPersistenceError from error
        except SQLAlchemyError as error:
            self._session.rollback()
            self._storage.cleanup_finalized(registered.finalized_upload)
            self._storage.cleanup_resumable(item.id)
            raise UploadBatchPersistenceError from error

        try:
            return self._finish_item(batch, item, UploadItemStatus.SUCCEEDED, photo_id=registered.photo.id)
        except UploadBatchPersistenceError:
            self._storage.cleanup_finalized(registered.finalized_upload)
            raise

    def cancel_batch(self, batch_id: UUID, owner_user_id: UUID) -> None:
        batch, items = self.get_batch(batch_id, owner_user_id, lock=True)
        if batch.status != UploadBatchStatus.ACTIVE:
            return
        for item in items:
            if UploadItemStatus(item.status) not in TERMINAL_ITEM_STATUSES:
                self._storage.cleanup_resumable(item.id)
                item.status = UploadItemStatus.FAILED
                item.error_code = "canceled"
                item.completed_at = datetime.now(UTC)
        batch.status = UploadBatchStatus.CANCELED
        batch.completed_at = datetime.now(UTC)
        self._commit()

    def _get_item(self, item_id: UUID, owner_user_id: UUID, *, lock: bool = False) -> tuple[UploadBatch, UploadItem]:
        statement = (
            select(UploadBatch, UploadItem)
            .join(UploadItem, UploadItem.batch_id == UploadBatch.id)
            .where(UploadItem.id == item_id, UploadBatch.owner_user_id == owner_user_id)
        )
        if lock:
            statement = statement.with_for_update()
        row = self._session.execute(statement).one_or_none()
        if row is None:
            raise UploadItemNotFoundError
        return row

    def _require_active(self, batch: UploadBatch, item: UploadItem) -> None:
        if batch.status == UploadBatchStatus.ACTIVE and batch.expires_at <= datetime.now(UTC):
            items = list(
                self._session.scalars(select(UploadItem).where(UploadItem.batch_id == batch.id).with_for_update()).all()
            )
            self._expire_batch(batch, items)
        if batch.status != UploadBatchStatus.ACTIVE:
            raise UploadBatchInvalidError("Upload batch is no longer active")
        if UploadItemStatus(item.status) in TERMINAL_ITEM_STATUSES:
            raise UploadBatchInvalidError("Upload item is already complete")

    def _cancel_batch_after_access_revocation(self, batch: UploadBatch) -> None:
        now = datetime.now(UTC)
        items = list(
            self._session.scalars(select(UploadItem).where(UploadItem.batch_id == batch.id).with_for_update()).all()
        )
        for item in items:
            if UploadItemStatus(item.status) in TERMINAL_ITEM_STATUSES:
                continue
            self._storage.cleanup_resumable(item.id)
            item.status = UploadItemStatus.FAILED
            item.error_code = "sharing_access_revoked"
            item.completed_at = now
        batch.status = UploadBatchStatus.CANCELED
        batch.completed_at = now
        self._commit()

    def _finish_item(
        self,
        batch: UploadBatch,
        item: UploadItem,
        status: UploadItemStatus,
        *,
        error_code: str | None = None,
        photo_id: UUID | None = None,
    ) -> UploadItem:
        item.status = status
        item.error_code = error_code
        item.photo_id = photo_id
        item.completed_at = datetime.now(UTC)
        remaining = self._session.scalar(
            select(func.count())
            .select_from(UploadItem)
            .where(
                UploadItem.batch_id == batch.id,
                UploadItem.id != item.id,
                UploadItem.status.not_in([status.value for status in TERMINAL_ITEM_STATUSES]),
            )
        )
        if not remaining:
            batch.status = UploadBatchStatus.COMPLETED
            batch.completed_at = datetime.now(UTC)
        self._commit()
        return item

    def _expire_stale_batches(self, *, commit: bool = True) -> None:
        batches = list(
            self._session.scalars(
                select(UploadBatch)
                .where(
                    UploadBatch.status == UploadBatchStatus.ACTIVE,
                    UploadBatch.expires_at <= datetime.now(UTC),
                )
                .with_for_update()
            ).all()
        )
        for batch in batches:
            items = list(
                self._session.scalars(select(UploadItem).where(UploadItem.batch_id == batch.id).with_for_update()).all()
            )
            self._expire_batch(batch, items, commit=False)
        if batches and commit:
            self._commit()

    def _expire_batch(self, batch: UploadBatch, items: list[UploadItem], *, commit: bool = True) -> None:
        now = datetime.now(UTC)
        for item in items:
            if UploadItemStatus(item.status) not in TERMINAL_ITEM_STATUSES:
                self._storage.cleanup_resumable(item.id)
                item.status = UploadItemStatus.FAILED
                item.error_code = "expired"
                item.completed_at = now
        batch.status = UploadBatchStatus.CANCELED
        batch.completed_at = now
        if commit:
            self._commit()

    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise UploadBatchPersistenceError from error


def _is_duplicate_photo_integrity_error(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None) == DUPLICATE_PHOTO_CONSTRAINT


def _storage_status(error: Exception) -> StorageStatusCode | None:
    if isinstance(error, StorageUnavailableError):
        return error.status
    if isinstance(error, PhotoUploadStorageError):
        return error.storage_status
    return None
