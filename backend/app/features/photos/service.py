import base64
import binascii
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.albums.public import remove_photo_from_group_albums
from app.features.audit.public import record_administrative_event
from app.features.groups.public import get_user_group_ids, lock_group_admin, lock_user_group_ids
from app.features.notifications.public import NotificationType, enqueue_group_notification
from app.features.photos.access import photo_is_in_library
from app.features.photos.models import (
    Photo,
    PhotoActivityEventType,
    PhotoDerivativeKind,
    PhotoFavorite,
    PhotoLifecycleState,
    PhotoShare,
)
from app.features.photos.registration import (
    DuplicatePhotoError,
    InvalidPhotoError,
    PhotoUploadStorageError,
    UnsupportedPhotoTypeError,
    build_sidecar_metadata,
    create_photo_activity_event,
    register_staged_photo,
)
from app.features.photos.storage import (
    PhotoStorage,
    PhotoStorageError,
    SidecarMetadata,
    StorageStatusCode,
    StorageUnavailableError,
    UploadTooLargeError,
)

logger = logging.getLogger(__name__)


class PhotoNotFoundError(Exception):
    def __init__(self, photo_id: UUID) -> None:
        super().__init__(f"Photo {photo_id} was not found")
        self.photo_id = photo_id


class PhotoUpdateForbiddenError(Exception):
    pass


class PhotoUpdateConflictError(Exception):
    pass


class PhotoUpdatePersistenceError(Exception):
    pass


class PhotoUpdateStorageError(Exception):
    pass


class PhotoContentUnavailableError(Exception):
    def __init__(self, photo_id: UUID) -> None:
        super().__init__(f"Content for photo {photo_id} is unavailable")
        self.photo_id = photo_id


class PhotoTooLargeError(Exception):
    pass


class PhotoUploadPersistenceError(Exception):
    pass


class InvalidPhotoSharingError(Exception):
    pass


class PhotoBulkSelectionError(Exception):
    pass


class PhotoExportSelectionError(Exception):
    pass


class PhotoDeleteStorageError(Exception):
    pass


class PhotoDeletePersistenceError(Exception):
    pass


class InvalidTrashCursorError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PhotoContent:
    path: Path
    content_type: str


@dataclass(frozen=True, slots=True)
class PhotoExportEntry:
    photo_id: UUID
    path: Path
    original_filename: str


@dataclass(frozen=True, slots=True)
class BulkPhotoSharingResult:
    operation_id: UUID
    updated_count: int
    unchanged_count: int


@dataclass(frozen=True, slots=True)
class TrashedPhotoPage:
    items: list[Photo]
    favorite_photo_ids: set[UUID]
    next_cursor: str | None
    total_count: int


class PhotoService:
    def __init__(
        self,
        session: Session,
        storage: PhotoStorage,
        default_timezone: str,
        trash_retention_days: int = 30,
    ) -> None:
        self._session = session
        self._storage = storage
        self._default_timezone = default_timezone
        self._trash_retention_days = trash_retention_days

    def get_photo(self, photo_id: UUID, viewer_user_id: UUID) -> Photo:
        statement = select(Photo).where(Photo.id == photo_id, self._can_view(viewer_user_id))
        photo = self._session.scalar(statement)
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        return photo

    def list_trashed_photos(
        self,
        owner_user_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> TrashedPhotoPage:
        conditions = [
            Photo.uploaded_by_user_id == owner_user_id,
            Photo.lifecycle_state.in_((PhotoLifecycleState.TRASHED, PhotoLifecycleState.PURGE_PENDING)),
        ]
        total_count = self._session.scalar(select(func.count()).select_from(Photo).where(*conditions)) or 0
        if cursor:
            trashed_at, photo_id = self._decode_trash_cursor(cursor)
            conditions.append(
                or_(Photo.trashed_at < trashed_at, and_(Photo.trashed_at == trashed_at, Photo.id < photo_id))
            )
        rows = list(
            self._session.scalars(
                select(Photo).where(*conditions).order_by(Photo.trashed_at.desc(), Photo.id.desc()).limit(limit + 1)
            ).all()
        )
        has_more = len(rows) > limit
        items = rows[:limit]
        favorite_photo_ids = set(
            self._session.scalars(
                select(PhotoFavorite.photo_id).where(
                    PhotoFavorite.user_id == owner_user_id,
                    PhotoFavorite.photo_id.in_([photo.id for photo in items]),
                )
            ).all()
        )
        next_cursor = None
        if has_more and items:
            last = items[-1]
            if last.trashed_at is None:
                raise RuntimeError("Trashed photos must have trashed_at")
            next_cursor = self._encode_trash_cursor(last.trashed_at, last.id)
        return TrashedPhotoPage(items, favorite_photo_ids, next_cursor, total_count)

    def get_trashed_photo(self, photo_id: UUID, owner_user_id: UUID) -> Photo:
        photo = self._session.scalar(
            select(Photo).where(
                Photo.id == photo_id,
                Photo.uploaded_by_user_id == owner_user_id,
                Photo.lifecycle_state.in_((PhotoLifecycleState.TRASHED, PhotoLifecycleState.PURGE_PENDING)),
            )
        )
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        return photo

    def get_trashed_photo_thumbnail(self, photo_id: UUID, owner_user_id: UUID) -> PhotoContent:
        photo = self.get_trashed_photo(photo_id, owner_user_id)
        derivative = photo.get_derivative(PhotoDerivativeKind.THUMBNAIL)
        if derivative is None:
            raise PhotoContentUnavailableError(photo_id)
        try:
            path = self._storage.get_derivative_path(derivative.storage_key)
        except PhotoStorageError as error:
            raise PhotoContentUnavailableError(photo_id) from error
        return PhotoContent(path=path, content_type=derivative.content_type)

    def trash_photo(self, photo_id: UUID, owner_user_id: UUID) -> Photo:
        photo = self._lock_owned_photo(photo_id, owner_user_id, PhotoLifecycleState.ACTIVE)
        now = datetime.now(UTC)
        previous_metadata = build_sidecar_metadata(photo)
        photo.lifecycle_state = PhotoLifecycleState.TRASHED
        photo.trashed_at = now
        photo.trashed_by_user_id = owner_user_id
        photo.purge_after = now + timedelta(days=self._trash_retention_days)
        photo.purge_requested_at = None
        self._commit_lifecycle_change(photo, previous_metadata)
        return photo

    def restore_photo(self, photo_id: UUID, owner_user_id: UUID) -> Photo:
        photo = self._lock_owned_photo(photo_id, owner_user_id, PhotoLifecycleState.TRASHED)
        previous_metadata = build_sidecar_metadata(photo)
        photo.lifecycle_state = PhotoLifecycleState.ACTIVE
        photo.trashed_at = None
        photo.trashed_by_user_id = None
        photo.purge_after = None
        photo.purge_requested_at = None
        self._commit_lifecycle_change(photo, previous_metadata)
        return photo

    def permanently_delete_photo(self, photo_id: UUID, owner_user_id: UUID) -> None:
        photo = self._session.scalar(
            select(Photo)
            .where(
                Photo.id == photo_id,
                Photo.uploaded_by_user_id == owner_user_id,
                Photo.lifecycle_state.in_((PhotoLifecycleState.TRASHED, PhotoLifecycleState.PURGE_PENDING)),
            )
            .with_for_update()
        )
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        if photo.lifecycle_state == PhotoLifecycleState.TRASHED:
            previous_metadata = build_sidecar_metadata(photo)
            photo.lifecycle_state = PhotoLifecycleState.PURGE_PENDING
            photo.purge_requested_at = datetime.now(UTC)
            self._commit_lifecycle_change(photo, previous_metadata)
        self._delete_pending_photo(photo)

    def purge_due_photos(self, *, limit: int = 100) -> int:
        now = datetime.now(UTC)
        photo_ids = list(
            self._session.scalars(
                select(Photo.id)
                .where(
                    Photo.lifecycle_state.in_((PhotoLifecycleState.TRASHED, PhotoLifecycleState.PURGE_PENDING)),
                    Photo.purge_after <= now,
                )
                .order_by(Photo.purge_after, Photo.id)
                .limit(limit)
            ).all()
        )
        purged = 0
        for photo_id in photo_ids:
            photo = self._session.scalar(select(Photo).where(Photo.id == photo_id).with_for_update())
            if photo is None or photo.lifecycle_state == PhotoLifecycleState.ACTIVE:
                self._session.rollback()
                continue
            if photo.lifecycle_state == PhotoLifecycleState.TRASHED:
                previous_metadata = build_sidecar_metadata(photo)
                photo.lifecycle_state = PhotoLifecycleState.PURGE_PENDING
                photo.purge_requested_at = datetime.now(UTC)
                self._commit_lifecycle_change(photo, previous_metadata)
            self._delete_pending_photo(photo)
            purged += 1
        return purged

    def is_favorite(self, photo_id: UUID, user_id: UUID) -> bool:
        return self._session.get(PhotoFavorite, (user_id, photo_id)) is not None

    def set_favorite(self, photo_id: UUID, user_id: UUID, favorite: bool) -> Photo:
        photo = self.get_photo(photo_id, user_id)
        record = self._session.get(PhotoFavorite, (user_id, photo_id))
        if favorite and record is None:
            self._session.add(PhotoFavorite(user_id=user_id, photo_id=photo_id, created_at=datetime.now(UTC)))
        elif not favorite and record is not None:
            self._session.delete(record)
        self._commit_favorite()
        return photo

    def get_photo_content(self, photo_id: UUID, viewer_user_id: UUID) -> PhotoContent:
        photo = self.get_photo(photo_id, viewer_user_id)
        try:
            path = self._storage.get_original_path(photo.storage_key)
        except PhotoStorageError as error:
            raise PhotoContentUnavailableError(photo_id) from error
        return PhotoContent(path=path, content_type=photo.content_type)

    def get_photo_thumbnail(self, photo_id: UUID, viewer_user_id: UUID) -> PhotoContent:
        photo = self.get_photo(photo_id, viewer_user_id)
        derivative = photo.get_derivative(PhotoDerivativeKind.THUMBNAIL)
        if derivative is None:
            raise PhotoContentUnavailableError(photo_id)
        try:
            path = self._storage.get_derivative_path(derivative.storage_key)
        except PhotoStorageError as error:
            raise PhotoContentUnavailableError(photo_id) from error
        return PhotoContent(path=path, content_type=derivative.content_type)

    def get_photo_export_entries(self, photo_ids: list[UUID], owner_user_id: UUID) -> list[PhotoExportEntry]:
        photos = list(
            self._session.scalars(
                select(Photo).where(
                    Photo.id.in_(photo_ids),
                    Photo.uploaded_by_user_id == owner_user_id,
                    Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
                )
            ).all()
        )
        photos_by_id = {photo.id: photo for photo in photos}
        if set(photos_by_id) != set(photo_ids):
            raise PhotoExportSelectionError

        entries = []
        for photo_id in photo_ids:
            photo = photos_by_id[photo_id]
            try:
                path = self._storage.get_original_path(photo.storage_key)
            except PhotoStorageError as error:
                raise PhotoContentUnavailableError(photo.id) from error
            entries.append(
                PhotoExportEntry(
                    photo_id=photo.id,
                    path=path,
                    original_filename=photo.original_filename,
                )
            )
        return entries

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
        captured_at_override: datetime | None = None,
        update_captured_at_override: bool = False,
    ) -> Photo:
        if sharing_group_ids is not None:
            candidate = self._session.scalar(select(Photo).where(Photo.id == photo_id, self._can_view(acting_user_id)))
            if candidate is None:
                raise PhotoNotFoundError(photo_id)
            if candidate.uploaded_by_user_id != acting_user_id:
                raise PhotoUpdateForbiddenError
            if lock_user_group_ids(self._session, acting_user_id, sharing_group_ids) != sharing_group_ids:
                raise InvalidPhotoSharingError
        photo = self._session.scalar(
            select(Photo).where(Photo.id == photo_id, self._can_view(acting_user_id)).with_for_update()
        )
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        if (
            sharing_group_ids is not None or update_captured_at_override
        ) and photo.uploaded_by_user_id != acting_user_id:
            raise PhotoUpdateForbiddenError
        if photo.metadata_version != expected_version:
            raise PhotoUpdateConflictError
        previous_metadata = build_sidecar_metadata(photo)
        previous_group_ids = {share.group_id for share in photo.shares}
        if update_memo:
            photo.metadata_record.memo = memo
            photo.metadata_record.memo_updated_by_user_id = acting_user_id
            photo.metadata_record.memo_updated_by_username = acting_username
            photo.metadata_record.memo_updated_at = datetime.now(UTC)
        if update_captured_at_override:
            if captured_at_override is not None and (
                captured_at_override.tzinfo is None or captured_at_override.utcoffset() is None
            ):
                raise PhotoUpdatePersistenceError("Capture time override must be timezone-aware")
            photo.metadata_record.captured_at_override = (
                captured_at_override.astimezone(UTC) if captured_at_override is not None else None
            )
        if sharing_group_ids is not None:
            shared_at = datetime.now(UTC)
            photo.shares[:] = []
            photo.shares.extend(
                PhotoShare(
                    id=uuid4(),
                    photo_id=photo.id,
                    group_id=group_id,
                    created_at=shared_at,
                )
                for group_id in sorted(sharing_group_ids, key=str)
            )
            activity_event = create_photo_activity_event(
                photo.id,
                acting_user_id,
                acting_username,
                PhotoActivityEventType.SHARED,
                sharing_group_ids - previous_group_ids,
                shared_at,
            )
            if activity_event is not None:
                self._session.add(activity_event)
                enqueue_group_notification(
                    self._session,
                    sharing_group_ids - previous_group_ids,
                    NotificationType.PHOTO_SHARED,
                    f"photo:{activity_event.operation_id}",
                    {"url": "/photos/new", "operation_id": str(activity_event.operation_id)},
                    exclude_user_id=acting_user_id,
                )
            remove_photo_from_group_albums(
                self._session,
                photo.id,
                previous_group_ids - sharing_group_ids,
            )
        photo.metadata_record.version += 1
        photo.metadata_record.updated_at = datetime.now(UTC)
        next_metadata = build_sidecar_metadata(photo)
        try:
            self._storage.update_sidecar(next_metadata)
        except PhotoStorageError as error:
            self._session.rollback()
            raise PhotoUpdateStorageError("Could not update photo sidecar") from error
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            try:
                self._storage.update_sidecar(previous_metadata)
            except PhotoStorageError:
                logger.exception(
                    "Failed to restore photo sidecar after database commit failure photo_id=%s storage_key=%s",
                    previous_metadata.photo_id,
                    previous_metadata.storage_key,
                )
            raise PhotoUpdatePersistenceError("Could not update photo metadata") from error
        return photo

    def remove_group_share_as_admin(
        self,
        photo_id: UUID,
        group_id: UUID,
        acting_user_id: UUID,
        acting_username: str,
    ) -> Photo:
        if lock_group_admin(self._session, group_id, acting_user_id) is None:
            raise PhotoUpdateForbiddenError
        photo = self._session.scalar(
            select(Photo)
            .where(Photo.id == photo_id, Photo.lifecycle_state == PhotoLifecycleState.ACTIVE)
            .with_for_update()
        )
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        share = next((item for item in photo.shares if item.group_id == group_id), None)
        if share is None:
            raise PhotoNotFoundError(photo_id)

        previous_metadata = build_sidecar_metadata(photo)
        photo.shares.remove(share)
        remove_photo_from_group_albums(self._session, photo.id, {group_id})
        photo.metadata_record.version += 1
        photo.metadata_record.updated_at = datetime.now(UTC)
        record_administrative_event(
            self._session,
            scope="group",
            action="photo.share_removed",
            actor_user_id=acting_user_id,
            actor_username=acting_username,
            group_id=group_id,
            target_type="photo",
            target_id=str(photo.id),
            details={"uploaded_by_username": photo.uploaded_by_username},
        )
        try:
            self._storage.update_sidecar(build_sidecar_metadata(photo))
        except PhotoStorageError as error:
            self._session.rollback()
            raise PhotoUpdateStorageError("Could not update photo sidecar") from error
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            try:
                self._storage.update_sidecar(previous_metadata)
            except PhotoStorageError:
                logger.exception(
                    "Failed to restore photo sidecar after group share moderation failure photo_id=%s group_id=%s",
                    photo.id,
                    group_id,
                )
            raise PhotoUpdatePersistenceError("Could not remove photo group share") from error
        return photo

    def bulk_add_sharing(
        self,
        photo_ids: list[UUID],
        add_group_ids: set[UUID],
        acting_user_id: UUID,
        acting_username: str,
    ) -> BulkPhotoSharingResult:
        if lock_user_group_ids(self._session, acting_user_id, add_group_ids) != add_group_ids:
            raise InvalidPhotoSharingError
        photos = list(
            self._session.scalars(
                select(Photo)
                .where(
                    Photo.id.in_(photo_ids),
                    Photo.uploaded_by_user_id == acting_user_id,
                    Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
                )
                .order_by(Photo.id)
                .with_for_update()
            ).all()
        )
        if {photo.id for photo in photos} != set(photo_ids):
            self._session.rollback()
            raise PhotoBulkSelectionError

        operation_id = uuid4()
        shared_at = datetime.now(UTC)
        previous_metadata = []
        changed_photos = []
        for photo in photos:
            current_group_ids = {share.group_id for share in photo.shares}
            new_group_ids = add_group_ids - current_group_ids
            if not new_group_ids:
                continue
            previous_metadata.append(build_sidecar_metadata(photo))
            photo.shares.extend(
                PhotoShare(
                    id=uuid4(),
                    photo_id=photo.id,
                    group_id=group_id,
                    created_at=shared_at,
                )
                for group_id in sorted(new_group_ids, key=str)
            )
            photo.metadata_record.version += 1
            photo.metadata_record.updated_at = shared_at
            activity_event = create_photo_activity_event(
                photo.id,
                acting_user_id,
                acting_username,
                PhotoActivityEventType.SHARED,
                new_group_ids,
                shared_at,
                operation_id=operation_id,
            )
            if activity_event is not None:
                self._session.add(activity_event)
                enqueue_group_notification(
                    self._session,
                    new_group_ids,
                    NotificationType.PHOTO_SHARED,
                    f"photo:{operation_id}",
                    {"url": "/photos/new", "operation_id": str(operation_id)},
                    exclude_user_id=acting_user_id,
                )
            changed_photos.append(photo)

        updated_sidecar_count = 0
        try:
            for photo in changed_photos:
                self._storage.update_sidecar(build_sidecar_metadata(photo))
                updated_sidecar_count += 1
        except PhotoStorageError as error:
            self._session.rollback()
            self._restore_sidecars(previous_metadata[:updated_sidecar_count])
            raise PhotoUpdateStorageError("Could not update photo sidecars") from error
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            self._restore_sidecars(previous_metadata)
            raise PhotoUpdatePersistenceError("Could not update photo sharing") from error
        return BulkPhotoSharingResult(
            operation_id=operation_id,
            updated_count=len(changed_photos),
            unchanged_count=len(photos) - len(changed_photos),
        )

    @classmethod
    def _can_view(cls, viewer_user_id: UUID):
        return photo_is_in_library(viewer_user_id)

    def upload_photo(
        self,
        source: BinaryIO,
        original_filename: str,
        declared_content_type: str | None,
        uploaded_by_user_id: UUID,
        uploaded_by_username: str,
        group_ids: set[UUID] | None = None,
    ) -> Photo:
        resolved_group_ids = group_ids or set()
        if get_user_group_ids(self._session, uploaded_by_user_id, resolved_group_ids) != resolved_group_ids:
            raise InvalidPhotoSharingError
        photo_id = uuid4()
        staged = None
        try:
            staged = self._storage.stage_upload(source, photo_id)
            if lock_user_group_ids(self._session, uploaded_by_user_id, resolved_group_ids) != resolved_group_ids:
                raise InvalidPhotoSharingError
            registered = register_staged_photo(
                self._session,
                self._storage,
                self._default_timezone,
                staged,
                original_filename,
                declared_content_type,
                uploaded_by_user_id,
                uploaded_by_username,
                group_ids=resolved_group_ids,
            )
            self._session.add(registered.photo)
            if registered.activity_event is not None:
                self._session.add(registered.activity_event)
                enqueue_group_notification(
                    self._session,
                    resolved_group_ids,
                    NotificationType.PHOTO_SHARED,
                    f"photo:{registered.activity_event.operation_id}",
                    {
                        "url": "/photos/new",
                        "operation_id": str(registered.activity_event.operation_id),
                    },
                    exclude_user_id=uploaded_by_user_id,
                )
            try:
                self._session.commit()
            except IntegrityError as error:
                self._session.rollback()
                self._storage.cleanup_finalized(registered.finalized_upload)
                raise DuplicatePhotoError("Photo was registered concurrently") from error
            except SQLAlchemyError as error:
                self._session.rollback()
                self._storage.cleanup_finalized(registered.finalized_upload)
                raise PhotoUploadPersistenceError("Could not register uploaded photo") from error
            return registered.photo
        except (DuplicatePhotoError, InvalidPhotoError, UnsupportedPhotoTypeError, PhotoUploadStorageError):
            self._session.rollback()
            raise
        except UploadTooLargeError as error:
            raise PhotoTooLargeError("Uploaded photo exceeds the size limit") from error
        except StorageUnavailableError as error:
            raise PhotoUploadStorageError(error.status) from error
        except PhotoStorageError as error:
            raise PhotoUploadStorageError(StorageStatusCode.IO_ERROR) from error
        finally:
            if staged is not None:
                self._storage.cleanup_staged(staged)

    def _commit_favorite(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PhotoUpdatePersistenceError("Could not update photo favorite") from error

    def _lock_owned_photo(self, photo_id: UUID, owner_user_id: UUID, state: PhotoLifecycleState) -> Photo:
        photo = self._session.scalar(
            select(Photo)
            .where(
                Photo.id == photo_id,
                Photo.uploaded_by_user_id == owner_user_id,
                Photo.lifecycle_state == state,
            )
            .with_for_update()
        )
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        return photo

    def _commit_lifecycle_change(self, photo: Photo, previous_metadata: SidecarMetadata) -> None:
        try:
            self._storage.update_sidecar(build_sidecar_metadata(photo))
        except PhotoStorageError as error:
            self._session.rollback()
            raise PhotoDeleteStorageError("Could not update photo lifecycle sidecar") from error
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            try:
                self._storage.update_sidecar(previous_metadata)
            except PhotoStorageError:
                logger.exception("Failed to restore lifecycle sidecar photo_id=%s", photo.id)
            raise PhotoDeletePersistenceError("Could not update photo lifecycle") from error

    def _delete_pending_photo(self, photo: Photo) -> None:
        derivative_keys = tuple(derivative.storage_key for derivative in photo.derivatives)
        try:
            self._storage.delete_photo_files(photo.storage_key, derivative_keys)
        except PhotoStorageError as error:
            self._session.rollback()
            raise PhotoDeleteStorageError("Could not permanently delete photo files") from error
        try:
            self._session.delete(photo)
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PhotoDeletePersistenceError("Could not remove permanently deleted photo record") from error

    def _restore_sidecars(self, metadata_records: list[SidecarMetadata]) -> None:
        for metadata in metadata_records:
            try:
                self._storage.update_sidecar(metadata)
            except PhotoStorageError:
                logger.exception(
                    "Failed to restore photo sidecar photo_id=%s storage_key=%s",
                    metadata.photo_id,
                    metadata.storage_key,
                )

    @staticmethod
    def _encode_trash_cursor(trashed_at: datetime, photo_id: UUID) -> str:
        payload = json.dumps(
            {"trashed_at": trashed_at.astimezone(UTC).isoformat(), "photo_id": str(photo_id)},
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_trash_cursor(value: str) -> tuple[datetime, UUID]:
        try:
            padding = "=" * (-len(value) % 4)
            payload = json.loads(base64.urlsafe_b64decode(value + padding))
            trashed_at = datetime.fromisoformat(payload["trashed_at"])
            photo_id = UUID(payload["photo_id"])
            if trashed_at.tzinfo is None or trashed_at.utcoffset() is None:
                raise ValueError
        except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise InvalidTrashCursorError("Invalid trash cursor") from error
        return trashed_at.astimezone(UTC), photo_id
