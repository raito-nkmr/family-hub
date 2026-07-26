from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.features.albums.models import Album, AlbumPhoto

__all__ = ["Album", "AlbumPhoto", "photo_is_in_album", "remove_photo_from_group_albums"]


def photo_is_in_album(photo_id, album_id):
    """Return a SQL predicate for membership in a specific album."""
    return exists(
        select(AlbumPhoto.photo_id).where(
            AlbumPhoto.photo_id == photo_id,
            AlbumPhoto.album_id == album_id,
        )
    )


def remove_photo_from_group_albums(session: Session, photo_id: UUID, group_ids: set[UUID]) -> None:
    """Remove a photo from albums whose group can no longer view it."""
    if not group_ids:
        return
    albums = list(
        session.scalars(
            select(Album)
            .where(
                Album.group_id.in_(group_ids),
                photo_is_in_album(photo_id, Album.id),
            )
            .with_for_update()
        ).all()
    )
    if not albums:
        return
    now = datetime.now(UTC)
    for album in albums:
        if album.cover_photo_id == photo_id:
            album.cover_photo_id = None
        album.updated_at = now
    session.flush()
    session.execute(
        delete(AlbumPhoto).where(
            AlbumPhoto.album_id.in_([album.id for album in albums]),
            AlbumPhoto.photo_id == photo_id,
        )
    )
