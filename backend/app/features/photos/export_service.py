from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.photos.models import Photo, PhotoLifecycleState
from app.features.photos.service import PhotoContentUnavailableError, PhotoExportEntry, PhotoExportSelectionError
from app.features.photos.storage import PhotoStorage, PhotoStorageError


class PhotoExportService:
    """Validates owner-selected originals for ZIP export."""

    def __init__(self, session: Session, storage: PhotoStorage) -> None:
        self._session = session
        self._storage = storage

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
            entries.append(PhotoExportEntry(photo.id, path, photo.original_filename))
        return entries
