from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.photos.access import photo_is_in_library
from app.features.photos.models import Photo, PhotoDerivativeKind, PhotoFavorite
from app.features.photos.service import (
    PhotoContent,
    PhotoContentUnavailableError,
    PhotoNotFoundError,
    PhotoUpdatePersistenceError,
)
from app.features.photos.storage import PhotoStorage, PhotoStorageError


class PhotoAccessService:
    """Reads photo metadata/content and manages per-user favorites."""

    def __init__(self, session: Session, storage: PhotoStorage) -> None:
        self._session = session
        self._storage = storage

    def get_photo(self, photo_id: UUID, viewer_user_id: UUID) -> Photo:
        photo = self._session.scalar(select(Photo).where(Photo.id == photo_id, photo_is_in_library(viewer_user_id)))
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        return photo

    def get_photo_content(self, photo_id: UUID, viewer_user_id: UUID) -> PhotoContent:
        photo = self.get_photo(photo_id, viewer_user_id)
        try:
            path = self._storage.get_original_path(photo.storage_key)
        except PhotoStorageError as error:
            raise PhotoContentUnavailableError(photo_id) from error
        return PhotoContent(path=path, content_type=photo.content_type)

    def get_photo_thumbnail(self, photo_id: UUID, viewer_user_id: UUID) -> PhotoContent:
        photo = self.get_photo(photo_id, viewer_user_id)
        derivative = photo.get_derivative(PhotoDerivativeKind.THUMBNAIL)
        if derivative is None:
            raise PhotoContentUnavailableError(photo_id)
        try:
            path = self._storage.get_derivative_path(derivative.storage_key)
        except PhotoStorageError as error:
            raise PhotoContentUnavailableError(photo_id) from error
        return PhotoContent(path=path, content_type=derivative.content_type)

    def is_favorite(self, photo_id: UUID, user_id: UUID) -> bool:
        return self._session.get(PhotoFavorite, (user_id, photo_id)) is not None

    def set_favorite(self, photo_id: UUID, user_id: UUID, favorite: bool) -> Photo:
        photo = self.get_photo(photo_id, user_id)
        record = self._session.get(PhotoFavorite, (user_id, photo_id))
        if favorite and record is None:
            self._session.add(PhotoFavorite(user_id=user_id, photo_id=photo_id, created_at=datetime.now(UTC)))
        elif not favorite and record is not None:
            self._session.delete(record)
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PhotoUpdatePersistenceError("Could not update photo favorite") from error
        return photo
