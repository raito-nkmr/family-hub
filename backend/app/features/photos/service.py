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
