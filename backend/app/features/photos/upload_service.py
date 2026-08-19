from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.groups.public import get_user_group_ids, lock_user_group_ids
from app.features.notifications.public import NotificationType, enqueue_group_notification
from app.features.photos.models import Photo
from app.features.photos.registration import (
    DuplicatePhotoError,
    InvalidPhotoError,
    PhotoUploadStorageError,
    UnsupportedPhotoTypeError,
    register_staged_photo,
)
from app.features.photos.service import (
    InvalidPhotoSharingError,
    PhotoTooLargeError,
    PhotoUploadPersistenceError,
)
from app.features.photos.storage import (
    PhotoStorage,
    PhotoStorageError,
    StorageStatusCode,
    StorageUnavailableError,
    UploadTooLargeError,
)


class PhotoUploadService:
    """Stages, registers, and commits one finalized photo upload."""

    def __init__(self, session: Session, storage: PhotoStorage, default_timezone: str) -> None:
        self._session = session
        self._storage = storage
        self._default_timezone = default_timezone

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
                    {"url": "/photos/new", "operation_id": str(registered.activity_event.operation_id)},
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
