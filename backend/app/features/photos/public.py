from collections.abc import Collection
from uuid import UUID

from fastapi import Request
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.features.groups.public import FamilyGroupMember
from app.features.photos.access import photo_is_in_library
from app.features.photos.album_sharing import (
    AlbumPhotoSharingError,
    AlbumPhotoSharingPermissionError,
    PhotoAlbumSharingService,
    PreparedAlbumPhotoShares,
)
from app.features.photos.models import Photo, PhotoFavorite, PhotoLifecycleState, PhotoMetadata, PhotoShare
from app.features.photos.schemas import PhotoResponse, photo_response_from_model
from app.features.photos.storage.facade import PhotoStorage
from app.features.photos.storage.types import StorageStatusCode

__all__ = [
    "Photo",
    "AlbumPhotoSharingError",
    "AlbumPhotoSharingPermissionError",
    "PhotoCatalog",
    "PhotoLifecycleState",
    "PhotoResponse",
    "PhotoShare",
    "PhotoStorage",
    "PhotoAlbumSharingService",
    "PreparedAlbumPhotoShares",
    "StorageStatusCode",
    "get_photo_storage",
    "photo_response_from_model",
    "visible_share_group_ids",
]


def visible_share_group_ids(
    session: Session,
    photo_ids: Collection[UUID],
    viewer_user_id: UUID,
) -> dict[UUID, set[UUID]]:
    if not photo_ids:
        return {}
    rows = session.execute(
        select(PhotoShare.photo_id, PhotoShare.group_id)
        .join(FamilyGroupMember, FamilyGroupMember.group_id == PhotoShare.group_id)
        .where(
            PhotoShare.photo_id.in_(photo_ids),
            FamilyGroupMember.user_id == viewer_user_id,
        )
    ).all()
    visible: dict[UUID, set[UUID]] = {photo_id: set() for photo_id in photo_ids}
    for photo_id, group_id in rows:
        visible[photo_id].add(group_id)
    return visible


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
        statement = select(Photo.id).where(
            Photo.id.in_(photo_ids),
            Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
            group_share,
        )
        return set(self._session.scalars(statement).all())

    def list_by_ids(self, photo_ids: Collection[UUID], viewer_user_id: UUID) -> list[Photo]:
        if not photo_ids:
            return []
        statement = (
            select(Photo)
            .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
            .where(Photo.id.in_(photo_ids), photo_is_in_library(viewer_user_id))
            .order_by(
                Photo.effective_captured_at.asc(),
                Photo.id.asc(),
            )
        )
        return list(self._session.scalars(statement).all())

    def favorite_photo_ids(self, photo_ids: Collection[UUID], viewer_user_id: UUID) -> set[UUID]:
        if not photo_ids:
            return set()
        statement = select(PhotoFavorite.photo_id).where(
            PhotoFavorite.user_id == viewer_user_id,
            PhotoFavorite.photo_id.in_(photo_ids),
        )
        return set(self._session.scalars(statement).all())

    def visible_share_group_ids(self, photo_ids: Collection[UUID], viewer_user_id: UUID) -> dict[UUID, set[UUID]]:
        return visible_share_group_ids(self._session, photo_ids, viewer_user_id)


async def get_photo_storage(request: Request) -> PhotoStorage:
    return PhotoStorage(request.app.state.settings)
