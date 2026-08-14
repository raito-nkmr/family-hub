from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.features.photos.models import Photo


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
    """Compatibility facade for tests and older integrations.

    Production routes depend on the feature-specific services directly. Keeping this
    lazy facade avoids making a broad breaking change for callers that still import
    the old service while the split is rolled out.
    """

    def __init__(
        self,
        session,
        storage,
        default_timezone: str,
        trash_retention_days: int = 30,
    ) -> None:
        from app.features.photos.access_service import PhotoAccessService
        from app.features.photos.export_service import PhotoExportService
        from app.features.photos.metadata_service import PhotoMetadataService
        from app.features.photos.trash_service import PhotoTrashService
        from app.features.photos.upload_service import PhotoUploadService

        self._services = (
            PhotoAccessService(session, storage),
            PhotoMetadataService(session, storage),
            PhotoUploadService(session, storage, default_timezone),
            PhotoTrashService(session, storage, trash_retention_days),
            PhotoExportService(session, storage),
        )

    def __getattr__(self, name: str):
        for service in self._services:
            method = getattr(service, name, None)
            if method is not None:
                return method
        raise AttributeError(name)
