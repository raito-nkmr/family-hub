from collections.abc import Collection
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.features.photos.access import photo_is_in_library
from app.features.photos.models import Photo, PhotoLifecycleState, PhotoMetadata, PhotoShare
from app.features.photos.schemas import PhotoResponse
from app.features.photos.storage import PhotoStorage, StorageStatusCode

__all__ = [
    "Photo",
    "PhotoCatalog",
    "PhotoLifecycleState",
    "PhotoResponse",
    "PhotoShare",
    "PhotoStorage",
    "StorageStatusCode",
]


class PhotoCatalog:
    """Read-only photo operations exposed to other features."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_addable_to_group_ids(self, photo_ids: Collection[UUID], group_id: UUID) -> set[UUID]:
        if not photo_ids:
            return set()
        group_share = exists(
            select(PhotoShare.id).where(
                PhotoShare.photo_id == Photo.id,
                PhotoShare.group_id == group_id,
            )
        )
        statement = select(Photo.id).where(Photo.id.in_(photo_ids), group_share)
        return set(self._session.scalars(statement).all())

    def list_by_ids(self, photo_ids: Collection[UUID], viewer_user_id: UUID) -> list[Photo]:
        if not photo_ids:
            return []
        statement = (
            select(Photo)
            .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
            .where(Photo.id.in_(photo_ids), photo_is_in_library(viewer_user_id))
            .order_by(
                func.coalesce(PhotoMetadata.captured_at_override, Photo.captured_at, Photo.uploaded_at).asc(),
                Photo.id.asc(),
            )
        )
        return list(self._session.scalars(statement).all())
