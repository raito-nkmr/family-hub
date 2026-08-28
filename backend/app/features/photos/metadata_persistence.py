import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.photos.errors import PhotoUpdatePersistenceError, PhotoUpdateStorageError
from app.features.photos.storage.facade import PhotoStorage, PhotoStorageError, SidecarMetadata

logger = logging.getLogger(__name__)


class PhotoMetadataPersistence:
    """Coordinate sidecar writes with the database transaction for metadata changes."""

    def __init__(self, session: Session, storage: PhotoStorage) -> None:
        self._session = session
        self._storage = storage

    def persist_and_commit(
        self,
        previous_metadata: SidecarMetadata,
        next_metadata: SidecarMetadata,
        *,
        storage_error: str,
        persistence_error: str,
    ) -> None:
        try:
            self._storage.update_sidecar(next_metadata)
        except PhotoStorageError as error:
            self._session.rollback()
            raise PhotoUpdateStorageError(storage_error) from error
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            self.restore_sidecars([previous_metadata])
            raise PhotoUpdatePersistenceError(persistence_error) from error

    def update_sidecar(self, metadata: SidecarMetadata) -> None:
        self._storage.update_sidecar(metadata)

    def restore_sidecars(self, metadata_records: list[SidecarMetadata]) -> None:
        for metadata in metadata_records:
            try:
                self._storage.update_sidecar(metadata)
            except PhotoStorageError:
                logger.exception("Failed to restore photo sidecar photo_id=%s", metadata.photo_id)
