"""Compatibility exports for the split photo error and type modules."""

from app.features.photos.errors import (
    InvalidPhotoSharingError,
    InvalidTrashCursorError,
    PhotoBulkSelectionError,
    PhotoContentUnavailableError,
    PhotoDeletePersistenceError,
    PhotoDeleteStorageError,
    PhotoExportSelectionError,
    PhotoNotFoundError,
    PhotoPurgeNotDueError,
    PhotoUpdateConflictError,
    PhotoUpdateForbiddenError,
    PhotoUpdatePersistenceError,
    PhotoUpdateStorageError,
)
from app.features.photos.types import BulkPhotoSharingResult, PhotoContent, PhotoExportEntry, TrashedPhotoPage

__all__ = [
    "BulkPhotoSharingResult",
    "InvalidPhotoSharingError",
    "InvalidTrashCursorError",
    "PhotoBulkSelectionError",
    "PhotoContent",
    "PhotoContentUnavailableError",
    "PhotoDeletePersistenceError",
    "PhotoDeleteStorageError",
    "PhotoExportEntry",
    "PhotoExportSelectionError",
    "PhotoNotFoundError",
    "PhotoPurgeNotDueError",
    "PhotoUpdateConflictError",
    "PhotoUpdateForbiddenError",
    "PhotoUpdatePersistenceError",
    "PhotoUpdateStorageError",
    "TrashedPhotoPage",
]
