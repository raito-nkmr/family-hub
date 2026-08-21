from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.features.photos.models import Photo


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
