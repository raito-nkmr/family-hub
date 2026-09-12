from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.features.albums.models import Album, AlbumGroupShare, AlbumPhoto
from app.features.groups.public import FamilyGroupMember

__all__ = [
    "Album",
    "AlbumGroupShare",
    "AlbumPhoto",
    "album_is_visible_to_user",
    "clear_photo_as_cover",
    "photo_is_in_album",
    "remove_photo_from_all_albums",
]


def photo_is_in_album(photo_id, album_id):
    """Return a SQL predicate for membership in a specific album."""
    return exists(
        select(AlbumPhoto.photo_id).where(
            AlbumPhoto.photo_id == photo_id,
            AlbumPhoto.album_id == album_id,
        )
    )


def album_is_visible_to_user(album_id, user_id):
    """Return a SQL predicate for membership in an accessible album group."""
    return exists(
        select(Album.id)
        .join(AlbumGroupShare, AlbumGroupShare.album_id == Album.id)
        .join(FamilyGroupMember, FamilyGroupMember.group_id == AlbumGroupShare.group_id)
        .where(
            Album.id == album_id,
            FamilyGroupMember.user_id == user_id,
        )
    )


def clear_photo_as_cover(session: Session, photo_id: UUID) -> None:
    """Clear a photo from every album that currently uses it as its cover."""
    albums = list(session.scalars(select(Album).where(Album.cover_photo_id == photo_id).with_for_update()).all())
    now = datetime.now(UTC)
    for album in albums:
        album.cover_photo_id = None
        album.updated_at = now
    if albums:
        session.flush()


def remove_photo_from_all_albums(session: Session, photo_id: UUID) -> None:
    """Remove a photo from every album when any of its group shares disappears."""
    albums = list(
        session.scalars(
            select(Album)
            .where(
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
