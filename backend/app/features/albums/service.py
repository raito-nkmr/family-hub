import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.albums.models import Album, AlbumPhoto
from app.features.groups.public import FamilyGroup, FamilyGroupMember, lock_user_group_ids
from app.features.photos.public import Photo, PhotoCatalog


class AlbumNotFoundError(Exception):
    def __init__(self, album_id: UUID) -> None:
        super().__init__(f"Album {album_id} was not found")
        self.album_id = album_id


class PhotoNotFoundError(Exception):
    def __init__(self, photo_ids: set[UUID]) -> None:
        super().__init__("One or more photos were not found")
        self.photo_ids = photo_ids


class PhotoNotInAlbumError(Exception):
    def __init__(self, album_id: UUID, photo_id: UUID) -> None:
        super().__init__(f"Photo {photo_id} is not in album {album_id}")
        self.album_id = album_id
        self.photo_id = photo_id


class AlbumPersistenceError(Exception):
    pass


class InvalidAlbumPhotoCursorError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AlbumSummary:
    id: UUID
    title: str
    description: str | None
    created_by_user_id: UUID
    created_by_username: str
    group_id: UUID
    group_name: str | None
    cover_photo_id: UUID | None
    created_at: datetime
    updated_at: datetime
    photo_count: int


@dataclass(frozen=True, slots=True)
class AlbumDetail:
    album: AlbumSummary
    photos: list[Photo]
    next_cursor: str | None = None


class AlbumService:
    def __init__(self, session: Session, photo_catalog: PhotoCatalog) -> None:
        self._session = session
        self._photo_catalog = photo_catalog

    def list_albums(self, viewer_user_id: UUID) -> list[AlbumSummary]:
        fallback_cover = (
            select(AlbumPhoto.photo_id)
            .where(AlbumPhoto.album_id == Album.id)
            .order_by(AlbumPhoto.added_at, AlbumPhoto.photo_id)
            .limit(1)
            .correlate(Album)
            .scalar_subquery()
        )
        statement = (
            select(
                Album,
                func.count(AlbumPhoto.photo_id),
                FamilyGroup.name,
                func.coalesce(Album.cover_photo_id, fallback_cover),
            )
            .outerjoin(AlbumPhoto, AlbumPhoto.album_id == Album.id)
            .outerjoin(FamilyGroup, FamilyGroup.id == Album.group_id)
            .where(self._can_access(viewer_user_id))
            .group_by(Album.id, FamilyGroup.name)
            .order_by(Album.updated_at.desc(), Album.id.desc())
        )
        return [
            self._summary(album, photo_count, group_name, cover_photo_id)
            for album, photo_count, group_name, cover_photo_id in self._session.execute(statement).all()
        ]

    def get_album(
        self,
        album_id: UUID,
        viewer_user_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> AlbumDetail:
        album = self._get_album_model(album_id, viewer_user_id)
        cursor_added_at, cursor_photo_id = self._decode_photo_cursor(cursor) if cursor else (None, None)
        page_statement = select(AlbumPhoto.photo_id, AlbumPhoto.added_at).where(AlbumPhoto.album_id == album_id)
        if cursor_added_at is not None and cursor_photo_id is not None:
            page_statement = page_statement.where(
                (AlbumPhoto.added_at > cursor_added_at)
                | ((AlbumPhoto.added_at == cursor_added_at) & (AlbumPhoto.photo_id > cursor_photo_id))
            )
        page_rows = self._session.execute(
            page_statement.order_by(AlbumPhoto.added_at, AlbumPhoto.photo_id).limit(limit + 1)
        ).all()
        has_more = len(page_rows) > limit
        visible_rows = page_rows[:limit]
        photo_ids = [row.photo_id for row in visible_rows]
        photos_by_id = {photo.id: photo for photo in self._photo_catalog.list_by_ids(photo_ids, viewer_user_id)}
        photos = [photos_by_id[photo_id] for photo_id in photo_ids if photo_id in photos_by_id]
        photo_count = self._session.scalar(
            select(func.count()).select_from(AlbumPhoto).where(AlbumPhoto.album_id == album_id)
        )
        group_name = self._session.scalar(select(FamilyGroup.name).where(FamilyGroup.id == album.group_id))
        fallback_cover_id = self._session.scalar(
            select(AlbumPhoto.photo_id)
            .where(AlbumPhoto.album_id == album_id)
            .order_by(AlbumPhoto.added_at, AlbumPhoto.photo_id)
            .limit(1)
        )
        next_cursor = None
        if has_more and visible_rows:
            last = visible_rows[-1]
            next_cursor = self._encode_photo_cursor(last.added_at, last.photo_id)
        return AlbumDetail(
            album=self._summary(album, photo_count or 0, group_name, album.cover_photo_id or fallback_cover_id),
            photos=photos,
            next_cursor=next_cursor,
        )

    def create_album(
        self,
        title: str,
        description: str | None,
        created_by_user_id: UUID,
        created_by_username: str,
        group_id: UUID,
    ) -> AlbumSummary:
        if lock_user_group_ids(self._session, created_by_user_id, {group_id}) != {group_id}:
            raise AlbumNotFoundError(group_id)
        now = datetime.now(UTC)
        album = Album(
            id=uuid4(),
            title=title,
            description=description,
            created_by_user_id=created_by_user_id,
            created_by_username=created_by_username,
            group_id=group_id,
            cover_photo_id=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(album)
        self._commit()
        group_name = self._session.scalar(select(FamilyGroup.name).where(FamilyGroup.id == group_id))
        return self._summary(album, 0, group_name, None)

    def update_album(
        self,
        album_id: UUID,
        title: str | None,
        description: str | None,
        update_description: bool,
        acting_user_id: UUID,
        cover_photo_id: UUID | None,
        update_cover: bool,
    ) -> AlbumSummary:
        album = self._get_album_model(album_id, acting_user_id, lock=True)
        if title is not None:
            album.title = title
        if update_description:
            album.description = description
        if update_cover:
            if cover_photo_id is not None and self._session.get(AlbumPhoto, (album_id, cover_photo_id)) is None:
                raise PhotoNotInAlbumError(album_id, cover_photo_id)
            album.cover_photo_id = cover_photo_id
        album.updated_at = datetime.now(UTC)
        self._commit()
        photo_count = self._session.scalar(
            select(func.count()).select_from(AlbumPhoto).where(AlbumPhoto.album_id == album_id)
        )
        group_name = self._session.scalar(select(FamilyGroup.name).where(FamilyGroup.id == album.group_id))
        fallback_cover_id = self._session.scalar(
            select(AlbumPhoto.photo_id)
            .where(AlbumPhoto.album_id == album_id)
            .order_by(AlbumPhoto.added_at, AlbumPhoto.photo_id)
            .limit(1)
        )
        return self._summary(album, photo_count or 0, group_name, album.cover_photo_id or fallback_cover_id)

    def delete_album(self, album_id: UUID, acting_user_id: UUID) -> None:
        album = self._get_album_model(album_id, acting_user_id, lock=True)
        self._session.delete(album)
        self._commit()

    def add_photos(self, album_id: UUID, photo_ids: list[UUID], acting_user_id: UUID) -> AlbumDetail:
        album = self._get_album_model(album_id, acting_user_id, lock=True)
        requested_ids = set(photo_ids)
        addable_ids = self._photo_catalog.get_addable_to_group_ids(requested_ids, album.group_id)
        missing_ids = requested_ids - addable_ids
        if missing_ids:
            raise PhotoNotFoundError(missing_ids)

        existing_ids = set(
            self._session.scalars(
                select(AlbumPhoto.photo_id).where(
                    AlbumPhoto.album_id == album_id,
                    AlbumPhoto.photo_id.in_(requested_ids),
                )
            ).all()
        )
        for photo_id in requested_ids - existing_ids:
            self._session.add(AlbumPhoto(album_id=album_id, photo_id=photo_id, added_at=datetime.now(UTC)))
        album.updated_at = datetime.now(UTC)
        self._commit()
        return self.get_album(album_id, acting_user_id)

    def remove_photo(self, album_id: UUID, photo_id: UUID, acting_user_id: UUID) -> None:
        album = self._get_album_model(album_id, acting_user_id, lock=True)
        if album.cover_photo_id == photo_id:
            album.cover_photo_id = None
            self._session.flush()
        result = self._session.execute(
            delete(AlbumPhoto).where(AlbumPhoto.album_id == album_id, AlbumPhoto.photo_id == photo_id)
        )
        if result.rowcount == 0:
            self._session.rollback()
            raise PhotoNotInAlbumError(album_id, photo_id)
        album.updated_at = datetime.now(UTC)
        self._commit()

    def _get_album_model(self, album_id: UUID, viewer_user_id: UUID, *, lock: bool = False) -> Album:
        if lock:
            candidate = self._session.scalar(
                select(Album).where(Album.id == album_id, self._can_access(viewer_user_id))
            )
            if candidate is None or lock_user_group_ids(self._session, viewer_user_id, {candidate.group_id}) != {
                candidate.group_id
            }:
                self._session.rollback()
                raise AlbumNotFoundError(album_id)
        statement = select(Album).where(Album.id == album_id, self._can_access(viewer_user_id))
        if lock:
            statement = statement.with_for_update()
        album = self._session.scalar(statement)
        if album is None:
            raise AlbumNotFoundError(album_id)
        return album

    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise AlbumPersistenceError("Could not persist album changes") from error

    @staticmethod
    def _summary(album: Album, photo_count: int, group_name: str | None, cover_photo_id: UUID | None) -> AlbumSummary:
        return AlbumSummary(
            id=album.id,
            title=album.title,
            description=album.description,
            created_by_user_id=album.created_by_user_id,
            created_by_username=album.created_by_username,
            group_id=album.group_id,
            group_name=group_name,
            cover_photo_id=cover_photo_id,
            created_at=album.created_at,
            updated_at=album.updated_at,
            photo_count=photo_count,
        )

    @staticmethod
    def _can_access(viewer_user_id: UUID):
        return Album.group_id.in_(select(FamilyGroupMember.group_id).where(FamilyGroupMember.user_id == viewer_user_id))

    @staticmethod
    def _encode_photo_cursor(added_at: datetime, photo_id: UUID) -> str:
        payload = json.dumps(
            {"added_at": added_at.astimezone(UTC).isoformat(), "photo_id": str(photo_id)},
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_photo_cursor(value: str) -> tuple[datetime, UUID]:
        try:
            padding = "=" * (-len(value) % 4)
            payload = json.loads(base64.urlsafe_b64decode(value + padding))
            added_at = datetime.fromisoformat(payload["added_at"])
            photo_id = UUID(payload["photo_id"])
            if added_at.tzinfo is None or added_at.utcoffset() is None:
                raise ValueError
        except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise InvalidAlbumPhotoCursorError("Invalid album photo cursor") from error
        return added_at.astimezone(UTC), photo_id
