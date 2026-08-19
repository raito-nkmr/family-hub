from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.photos.image_validation import InvalidImageError, inspect_image
from app.features.photos.models import (
    Photo,
    PhotoActivityEvent,
    PhotoActivityEventGroup,
    PhotoActivityEventType,
    PhotoDerivative,
    PhotoDerivativeKind,
    PhotoLifecycleState,
    PhotoMetadata,
    PhotoShare,
)
from app.features.photos.storage import (
    FinalizedUpload,
    PhotoStorage,
    PhotoStorageError,
    SidecarMetadata,
    StagedUpload,
    StorageStatusCode,
    StorageUnavailableError,
)
from app.features.photos.video_validation import VIDEO_CONTENT_TYPES, InvalidVideoError, inspect_video

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/heif", "image/heic", *VIDEO_CONTENT_TYPES}


class UnsupportedPhotoTypeError(Exception):
    pass


class InvalidPhotoError(Exception):
    pass


class DuplicatePhotoError(Exception):
    pass


class PhotoUploadStorageError(Exception):
    def __init__(self, storage_status: StorageStatusCode) -> None:
        super().__init__(f"Photo storage rejected upload: {storage_status}")
        self.storage_status = storage_status


@dataclass(frozen=True, slots=True)
class RegisteredPhoto:
    photo: Photo
    finalized_upload: FinalizedUpload
    activity_event: PhotoActivityEvent | None = None


def create_photo_activity_event(
    photo_id: UUID,
    actor_user_id: UUID,
    actor_username: str,
    event_type: PhotoActivityEventType,
    group_ids: set[UUID],
    occurred_at: datetime,
    *,
    operation_id: UUID | None = None,
) -> PhotoActivityEvent | None:
    if not group_ids:
        return None
    event_id = uuid4()
    return PhotoActivityEvent(
        id=event_id,
        photo_id=photo_id,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        event_type=event_type,
        operation_id=operation_id or uuid4(),
        occurred_at=occurred_at,
        groups=[
            PhotoActivityEventGroup(event_id=event_id, group_id=group_id) for group_id in sorted(group_ids, key=str)
        ],
    )


def register_staged_photo(
    session: Session,
    storage: PhotoStorage,
    default_timezone: str,
    staged: StagedUpload,
    original_filename: str,
    declared_content_type: str | None,
    uploaded_by_user_id: UUID,
    uploaded_by_username: str,
    *,
    group_ids: set[UUID] | None = None,
    activity_operation_id: UUID | None = None,
) -> RegisteredPhoto:
    """Prepare a photo and its files without committing or rolling back the database transaction."""
    if declared_content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedPhotoTypeError("Declared content type is not supported")

    try:
        try:
            if declared_content_type.startswith("video/"):
                image = inspect_video(staged.path, declared_content_type, default_timezone)
            else:
                image = inspect_image(staged.path, declared_content_type, default_timezone)
        except (InvalidImageError, InvalidVideoError) as error:
            raise InvalidPhotoError("Uploaded file is not a valid supported media file") from error

        duplicate = session.scalar(
            select(Photo.id).where(
                Photo.uploaded_by_user_id == uploaded_by_user_id,
                Photo.sha256 == staged.sha256,
            )
        )
        if duplicate is not None:
            raise DuplicatePhotoError("Photo with the same content is already registered")

        uploaded_at = datetime.now(UTC)
        storage_key = f"originals/{uploaded_at:%Y/%m}/{staged.photo_id}{image.extension}"
        thumbnail_key = f"thumbnails/{uploaded_at:%Y/%m}/{staged.photo_id}.webp"
        if image.content_type.startswith("video/"):
            thumbnail = storage.stage_thumbnail(staged.path, thumbnail_key, content_type=image.content_type)
        else:
            thumbnail = storage.stage_thumbnail(staged.path, thumbnail_key)
        photo = Photo(
            id=staged.photo_id,
            uploaded_by_user_id=uploaded_by_user_id,
            uploaded_by_username=uploaded_by_username,
            original_filename=original_filename,
            storage_key=storage_key,
            content_type=image.content_type,
            size_bytes=staged.size_bytes,
            sha256=staged.sha256,
            width=image.width,
            height=image.height,
            captured_at=image.captured_at,
            uploaded_at=uploaded_at,
            lifecycle_state=PhotoLifecycleState.ACTIVE,
            trashed_at=None,
            trashed_by_user_id=None,
            purge_after=None,
            purge_requested_at=None,
            derivatives=[
                PhotoDerivative(
                    id=uuid4(),
                    photo_id=staged.photo_id,
                    kind=PhotoDerivativeKind.THUMBNAIL,
                    storage_key=thumbnail.storage_key,
                    content_type=thumbnail.content_type,
                    width=thumbnail.width,
                    height=thumbnail.height,
                    size_bytes=thumbnail.size_bytes,
                    created_at=uploaded_at,
                )
            ],
            metadata_record=PhotoMetadata(
                photo_id=staged.photo_id,
                memo=None,
                memo_updated_by_user_id=uploaded_by_user_id,
                memo_updated_by_username=uploaded_by_username,
                memo_updated_at=uploaded_at,
                captured_at_override=None,
                version=1,
                created_at=uploaded_at,
                updated_at=uploaded_at,
            ),
            shares=[
                PhotoShare(
                    id=uuid4(),
                    photo_id=staged.photo_id,
                    group_id=group_id,
                    created_at=uploaded_at,
                )
                for group_id in sorted(group_ids or set(), key=str)
            ],
        )
        finalized = storage.finalize_upload(staged, thumbnail, build_sidecar_metadata(photo))
        activity_event = create_photo_activity_event(
            photo.id,
            uploaded_by_user_id,
            uploaded_by_username,
            PhotoActivityEventType.UPLOADED,
            group_ids or set(),
            uploaded_at,
            operation_id=activity_operation_id,
        )
        return RegisteredPhoto(photo=photo, finalized_upload=finalized, activity_event=activity_event)
    except StorageUnavailableError as error:
        raise PhotoUploadStorageError(error.status) from error
    except PhotoStorageError as error:
        raise PhotoUploadStorageError(StorageStatusCode.IO_ERROR) from error


def build_sidecar_metadata(photo: Photo) -> SidecarMetadata:
    return SidecarMetadata(
        photo_id=photo.id,
        uploaded_by_user_id=photo.uploaded_by_user_id,
        uploaded_by_username=photo.uploaded_by_username,
        memo=photo.memo,
        memo_updated_by_user_id=photo.memo_updated_by_user_id,
        memo_updated_by_username=photo.memo_updated_by_username,
        memo_updated_at=photo.memo_updated_at,
        metadata_version=photo.metadata_version,
        sharing_audiences=tuple(
            {
                "type": "group",
                "id": str(share.group_id),
            }
            for share in sorted(photo.shares, key=lambda share: str(share.group_id))
        ),
        original_filename=photo.original_filename,
        storage_key=photo.storage_key,
        content_type=photo.content_type,
        size_bytes=photo.size_bytes,
        sha256=photo.sha256,
        width=photo.width,
        height=photo.height,
        captured_at=photo.captured_at,
        captured_at_override=photo.metadata_record.captured_at_override,
        uploaded_at=photo.uploaded_at,
        derivatives=tuple(
            {
                "kind": str(derivative.kind),
                "storage_key": derivative.storage_key,
                "content_type": derivative.content_type,
                "width": derivative.width,
                "height": derivative.height,
                "size_bytes": derivative.size_bytes,
            }
            for derivative in sorted(photo.derivatives, key=lambda derivative: derivative.kind)
        ),
        lifecycle_state=str(photo.lifecycle_state),
        trashed_at=photo.trashed_at,
        trashed_by_user_id=photo.trashed_by_user_id,
        purge_after=photo.purge_after,
        purge_requested_at=photo.purge_requested_at,
    )
