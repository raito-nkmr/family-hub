from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.groups.public import lock_user_group_ids
from app.features.notifications.public import NotificationType, enqueue_group_notification
from app.features.photos.metadata_persistence import PhotoMetadataPersistence
from app.features.photos.models import Photo, PhotoActivityEventType, PhotoLifecycleState, PhotoShare
from app.features.photos.registration import build_sidecar_metadata, create_photo_activity_event
from app.features.photos.storage.facade import PhotoStorage, PhotoStorageError, SidecarMetadata


class AlbumPhotoSharingError(Exception):
    pass


class AlbumPhotoSharingPermissionError(AlbumPhotoSharingError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedAlbumPhotoShares:
    previous_metadata: tuple[SidecarMetadata, ...]


class PhotoAlbumSharingService:
    """Prepare photo shares needed to make an album visible to all target groups."""

    def __init__(self, session: Session, storage: PhotoStorage) -> None:
        self._session = session
        self._persistence = PhotoMetadataPersistence(session, storage)

    def prepare_add_groups(
        self,
        photo_group_ids: dict[UUID, set[UUID]],
        acting_user_id: UUID,
        acting_username: str,
    ) -> PreparedAlbumPhotoShares:
        if not photo_group_ids:
            return PreparedAlbumPhotoShares(())
        photo_ids = set(photo_group_ids)
        group_ids = set().union(*photo_group_ids.values())
        if lock_user_group_ids(self._session, acting_user_id, group_ids) != group_ids:
            raise AlbumPhotoSharingPermissionError
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
        if {photo.id for photo in photos} != photo_ids:
            raise AlbumPhotoSharingError("One or more photos are not owned by the acting user")

        previous_metadata: list[SidecarMetadata] = []
        operation_id = uuid4()
        shared_at = datetime.now(UTC)
        for photo in photos:
            current_group_ids = {share.group_id for share in photo.shares}
            new_group_ids = photo_group_ids[photo.id] - current_group_ids
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
                activity_operation_id=operation_id,
            )
            if activity_event is not None:
                self._session.add(activity_event)
                enqueue_group_notification(
                    self._session,
                    new_group_ids,
                    NotificationType.PHOTO_SHARED,
                    f"photo:{operation_id}",
                    {"url": "/photos/new", "activity_operation_id": str(operation_id)},
                    exclude_user_id=acting_user_id,
                )

        try:
            changed_photo_ids = {metadata.photo_id for metadata in previous_metadata}
            for photo in photos:
                if photo.id in changed_photo_ids:
                    self._persistence.update_sidecar(build_sidecar_metadata(photo))
        except PhotoStorageError as error:
            self._session.rollback()
            self._persistence.restore_sidecars(previous_metadata)
            raise AlbumPhotoSharingError("Could not update photo sidecars") from error
        return PreparedAlbumPhotoShares(tuple(previous_metadata))

    def commit(self, prepared: PreparedAlbumPhotoShares) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            self._persistence.restore_sidecars(list(prepared.previous_metadata))
            raise AlbumPhotoSharingError("Could not persist album photo sharing") from error
