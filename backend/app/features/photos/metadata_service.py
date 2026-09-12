from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.albums.public import remove_photo_from_all_albums
from app.features.audit.public import record_administrative_event
from app.features.groups.public import FamilyGroupMember, lock_group_admin, lock_user_group_ids
from app.features.notifications.public import NotificationType, enqueue_group_notification
from app.features.photos.errors import (
    InvalidPhotoSharingError,
    PhotoBulkSelectionError,
    PhotoNotFoundError,
    PhotoUpdateConflictError,
    PhotoUpdateForbiddenError,
    PhotoUpdatePersistenceError,
    PhotoUpdateStorageError,
)
from app.features.photos.metadata_persistence import PhotoMetadataPersistence
from app.features.photos.models import Photo, PhotoActivityEventType, PhotoLifecycleState, PhotoShare
from app.features.photos.registration import build_sidecar_metadata, create_photo_activity_event
from app.features.photos.storage.facade import PhotoStorage, PhotoStorageError, SidecarMetadata
from app.features.photos.types import BulkPhotoSharingResult


class PhotoMetadataService:
    """Updates memo, capture-time overrides, and sharing metadata."""

    def __init__(self, session: Session, storage: PhotoStorage) -> None:
        self._session = session
        self._persistence = PhotoMetadataPersistence(session, storage)

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
            candidate = self._session.scalar(
                select(Photo).where(Photo.id == photo_id, _photo_is_in_library(acting_user_id))
            )
            if candidate is None:
                raise PhotoNotFoundError(photo_id)
            if candidate.uploaded_by_user_id != acting_user_id:
                raise PhotoUpdateForbiddenError
            if lock_user_group_ids(self._session, acting_user_id, sharing_group_ids) != sharing_group_ids:
                raise InvalidPhotoSharingError
        photo = self._session.scalar(
            select(Photo).where(Photo.id == photo_id, _photo_is_in_library(acting_user_id)).with_for_update()
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
            normalized_override = captured_at_override.astimezone(UTC) if captured_at_override is not None else None
            photo.metadata_record.captured_at_override = normalized_override
            photo.effective_captured_at = normalized_override or photo.captured_at_original or photo.uploaded_at
        if sharing_group_ids is not None:
            visible_existing_group_ids = set(
                self._session.scalars(
                    select(FamilyGroupMember.group_id).where(
                        FamilyGroupMember.user_id == acting_user_id,
                        FamilyGroupMember.group_id.in_(previous_group_ids),
                    )
                ).all()
            )
            next_group_ids = set(sharing_group_ids) | (previous_group_ids - visible_existing_group_ids)
            shared_at = datetime.now(UTC)
            photo.shares[:] = []
            photo.shares.extend(
                PhotoShare(id=uuid4(), photo_id=photo.id, group_id=group_id, created_at=shared_at)
                for group_id in sorted(next_group_ids, key=str)
            )
            activity_event = create_photo_activity_event(
                photo.id,
                acting_user_id,
                acting_username,
                PhotoActivityEventType.SHARED,
                next_group_ids - previous_group_ids,
                shared_at,
            )
            if activity_event is not None:
                self._session.add(activity_event)
                enqueue_group_notification(
                    self._session,
                    next_group_ids - previous_group_ids,
                    NotificationType.PHOTO_SHARED,
                    f"photo:{activity_event.activity_operation_id}",
                    {"url": "/photos/new", "activity_operation_id": str(activity_event.activity_operation_id)},
                    exclude_user_id=acting_user_id,
                )
            if previous_group_ids - next_group_ids:
                remove_photo_from_all_albums(self._session, photo.id)
        photo.metadata_record.version += 1
        photo.metadata_record.updated_at = datetime.now(UTC)
        next_metadata = build_sidecar_metadata(photo)
        self._persistence.persist_and_commit(
            previous_metadata,
            next_metadata,
            storage_error="Could not update photo sidecar",
            persistence_error="Could not update photo metadata",
        )
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
        remove_photo_from_all_albums(self._session, photo.id)
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
        self._persistence.persist_and_commit(
            previous_metadata,
            build_sidecar_metadata(photo),
            storage_error="Could not update photo sidecar",
            persistence_error="Could not remove photo group share",
        )
        return photo

    def bulk_add_sharing(
        self,
        photo_ids: list[UUID],
        group_ids_to_add: set[UUID],
        acting_user_id: UUID,
        acting_username: str,
    ) -> BulkPhotoSharingResult:
        if lock_user_group_ids(self._session, acting_user_id, group_ids_to_add) != group_ids_to_add:
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
        activity_operation_id = uuid4()
        shared_at = datetime.now(UTC)
        previous_metadata: list[SidecarMetadata] = []
        changed_photos: list[Photo] = []
        for photo in photos:
            current_group_ids = {share.group_id for share in photo.shares}
            new_group_ids = group_ids_to_add - current_group_ids
            if not new_group_ids:
                continue
            previous_metadata.append(build_sidecar_metadata(photo))
            photo.shares.extend(
                PhotoShare(id=uuid4(), photo_id=photo.id, group_id=group_id, created_at=shared_at)
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
                activity_operation_id=activity_operation_id,
            )
            if activity_event is not None:
                self._session.add(activity_event)
                enqueue_group_notification(
                    self._session,
                    new_group_ids,
                    NotificationType.PHOTO_SHARED,
                    f"photo:{activity_operation_id}",
                    {"url": "/photos/new", "activity_operation_id": str(activity_operation_id)},
                    exclude_user_id=acting_user_id,
                )
            changed_photos.append(photo)
        updated_sidecar_count = 0
        try:
            for photo in changed_photos:
                self._persistence.update_sidecar(build_sidecar_metadata(photo))
                updated_sidecar_count += 1
        except PhotoStorageError as error:
            self._session.rollback()
            self._persistence.restore_sidecars(previous_metadata[:updated_sidecar_count])
            raise PhotoUpdateStorageError("Could not update photo sidecars") from error
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            self._persistence.restore_sidecars(previous_metadata)
            raise PhotoUpdatePersistenceError("Could not update photo sharing") from error
        return BulkPhotoSharingResult(
            activity_operation_id,
            len(changed_photos),
            len(photos) - len(changed_photos),
        )


def _photo_is_in_library(viewer_user_id: UUID):
    from app.features.photos.access import photo_is_in_library

    return photo_is_in_library(viewer_user_id)
