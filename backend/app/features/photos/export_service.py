from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.photos.access import photo_is_in_library
from app.features.photos.errors import PhotoContentUnavailableError, PhotoExportSelectionError
from app.features.photos.models import Photo
from app.features.photos.storage import PhotoStorage, PhotoStorageError
from app.features.photos.types import PhotoExportEntry


class PhotoExportService:
    """Validates originals selected from the viewer's accessible photo library."""

    def __init__(self, session: Session, storage: PhotoStorage) -> None:
        self._session = session
        self._storage = storage

    def get_photo_export_entries(self, photo_ids: list[UUID], viewer_user_id: UUID) -> list[PhotoExportEntry]:
        photos = list(
            self._session.scalars(
                select(Photo).where(
                    Photo.id.in_(photo_ids),
                    photo_is_in_library(viewer_user_id),
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
            entries.append(PhotoExportEntry(photo.id, path, photo.original_filename))
        return entries
