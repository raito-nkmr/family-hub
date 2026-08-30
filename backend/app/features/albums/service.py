import base64
import binascii
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from app.features.albums.models import Album, AlbumGroupShare, AlbumPhoto
from app.features.groups.public import FamilyGroup, FamilyGroupMember, lock_group_ids, lock_user_group_ids
from app.features.photos.public import (
    AlbumPhotoSharingError,
    AlbumPhotoSharingPermissionError,
    Photo,
    PhotoAlbumSharingService,
    PhotoCatalog,
    PhotoLifecycleState,
    PreparedAlbumPhotoShares,
)


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
    group_ids: list[UUID]
    group_names: list[str]
    cover_photo_id: UUID | None
    created_at: datetime
    updated_at: datetime
    photo_count: int


@dataclass(frozen=True, slots=True)
class AlbumDetail:
    album: AlbumSummary
    photos: list[Photo]
    next_cursor: str | None = None
    visible_group_ids: dict[UUID, set[UUID]] = field(default_factory=dict)
    favorite_photo_ids: set[UUID] = field(default_factory=set)


class AlbumService:
    def __init__(
        self,
        session: Session,
        photo_catalog: PhotoCatalog,
        photo_sharing: PhotoAlbumSharingService,
    ) -> None:
        self._session = session
        self._photo_catalog = photo_catalog
        self._photo_sharing = photo_sharing

    def list_albums(self, viewer_user_id: UUID) -> list[AlbumSummary]:
        fallback_cover = (
            select(AlbumPhoto.photo_id)
            .join(Photo, Photo.id == AlbumPhoto.photo_id)
            .where(
                AlbumPhoto.album_id == Album.id,
                Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
            )
            .order_by(
                case((AlbumPhoto.photo_id == Album.cover_photo_id, 0), else_=1),
                AlbumPhoto.added_at,
                AlbumPhoto.photo_id,
            )
            .limit(1)
            .correlate(Album)
            .scalar_subquery()
        )
        statement = (
            select(
                Album,
                func.count(Photo.id).filter(Photo.lifecycle_state == PhotoLifecycleState.ACTIVE),
                fallback_cover,
            )
            .outerjoin(AlbumPhoto, AlbumPhoto.album_id == Album.id)
            .outerjoin(Photo, Photo.id == AlbumPhoto.photo_id)
            .where(self._can_access(viewer_user_id))
            .group_by(Album.id)
            .order_by(Album.updated_at.desc(), Album.id.desc())
        )
        return [
            self._summary(album, photo_count, *self._group_details(album.id), cover_photo_id)
            for album, photo_count, cover_photo_id in self._session.execute(statement).all()
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
        cursor_sort_at, cursor_photo_id = self._decode_photo_cursor(cursor) if cursor else (None, None)
        page_statement = (
            select(AlbumPhoto.photo_id, Photo.effective_captured_at)
            .join(Photo, Photo.id == AlbumPhoto.photo_id)
            .where(
                AlbumPhoto.album_id == album_id,
                Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
            )
        )
        if cursor_sort_at is not None and cursor_photo_id is not None:
            page_statement = page_statement.where(
                (Photo.effective_captured_at > cursor_sort_at)
                | ((Photo.effective_captured_at == cursor_sort_at) & (Photo.id > cursor_photo_id))
            )
        page_rows = self._session.execute(
            page_statement.order_by(Photo.effective_captured_at, Photo.id).limit(limit + 1)
        ).all()
        has_more = len(page_rows) > limit
        visible_rows = page_rows[:limit]
        photo_ids = [row.photo_id for row in visible_rows]
        photos_by_id = {photo.id: photo for photo in self._photo_catalog.list_by_ids(photo_ids, viewer_user_id)}
        photos = [photos_by_id[photo_id] for photo_id in photo_ids if photo_id in photos_by_id]
        photo_count = self._session.scalar(
            select(func.count())
            .select_from(AlbumPhoto)
            .join(Photo, Photo.id == AlbumPhoto.photo_id)
            .where(
                AlbumPhoto.album_id == album_id,
                Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
            )
        )
        group_ids, group_names = self._group_details(album.id)
        fallback_cover_id = self._session.scalar(
            select(AlbumPhoto.photo_id)
            .join(Photo, Photo.id == AlbumPhoto.photo_id)
            .where(
                AlbumPhoto.album_id == album_id,
                Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
            )
            .order_by(
                case((AlbumPhoto.photo_id == album.cover_photo_id, 0), else_=1),
                AlbumPhoto.added_at,
                AlbumPhoto.photo_id,
            )
            .limit(1)
        )
        next_cursor = None
        if has_more and visible_rows:
            last = visible_rows[-1]
            next_cursor = self._encode_photo_cursor(last.effective_captured_at, last.photo_id)
        return AlbumDetail(
            album=self._summary(album, photo_count or 0, group_ids, group_names, fallback_cover_id),
            photos=photos,
            next_cursor=next_cursor,
            visible_group_ids=self._photo_catalog.visible_share_group_ids(photo_ids, viewer_user_id),
            favorite_photo_ids=self._photo_catalog.favorite_photo_ids(photo_ids, viewer_user_id),
        )

    def create_album(
        self,
        title: str,
        description: str | None,
        created_by_user_id: UUID,
        created_by_username: str,
        group_ids: list[UUID],
    ) -> AlbumSummary:
        requested_group_ids = set(group_ids)
        if not requested_group_ids:
            raise AlbumNotFoundError(UUID(int=0))
        if lock_user_group_ids(self._session, created_by_user_id, requested_group_ids) != requested_group_ids:
            raise AlbumNotFoundError(next(iter(requested_group_ids)))
        now = datetime.now(UTC)
        album = Album(
            id=uuid4(),
            title=title,
            description=description,
            created_by_user_id=created_by_user_id,
            created_by_username=created_by_username,
            cover_photo_id=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(album)
        self._session.flush()
        self._session.add_all(
            AlbumGroupShare(album_id=album.id, group_id=group_id, created_at=now)
            for group_id in sorted(requested_group_ids, key=str)
        )
        self._commit()
        return self._summary(album, 0, *self._group_details(album.id), None)

    def update_album(
        self,
        album_id: UUID,
        title: str | None,
        description: str | None,
        update_description: bool,
        acting_user_id: UUID,
        cover_photo_id: UUID | None,
        update_cover: bool,
        group_ids: list[UUID] | None = None,
        update_groups: bool = False,
        acting_username: str = "",
    ) -> AlbumSummary:
        album = self._get_album_model(album_id, acting_user_id, lock=True)
        if update_cover and cover_photo_id is not None:
            active_cover = self._session.scalar(
                select(Photo.id)
                .join(AlbumPhoto, AlbumPhoto.photo_id == Photo.id)
                .where(
                    AlbumPhoto.album_id == album_id,
                    AlbumPhoto.photo_id == cover_photo_id,
                    Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
                )
            )
            if active_cover is None:
                raise PhotoNotInAlbumError(album_id, cover_photo_id)
        prepared_shares = PreparedAlbumPhotoShares(())
        if update_groups:
            requested_group_ids = set(group_ids or [])
            if not requested_group_ids:
                raise AlbumNotFoundError(album_id)
            current_group_ids = set(self._group_ids(album.id))
            added_group_ids = requested_group_ids - current_group_ids
            if lock_user_group_ids(self._session, acting_user_id, added_group_ids) != added_group_ids:
                raise AlbumNotFoundError(album_id)
            lock_group_ids(self._session, current_group_ids | requested_group_ids)
            prepared_shares = self._prepare_album_photo_sharing(
                album.id,
                requested_group_ids,
                acting_user_id,
                set(self._album_photo_ids(album.id)),
                acting_username,
            )
            self._session.execute(
                delete(AlbumGroupShare).where(
                    AlbumGroupShare.album_id == album.id,
                    ~AlbumGroupShare.group_id.in_(requested_group_ids),
                )
            )
            existing_group_ids = current_group_ids & requested_group_ids
            self._session.add_all(
                AlbumGroupShare(album_id=album.id, group_id=group_id, created_at=datetime.now(UTC))
                for group_id in sorted(requested_group_ids - existing_group_ids, key=str)
            )
        if title is not None:
            album.title = title
        if update_description:
            album.description = description
        if update_cover:
            album.cover_photo_id = cover_photo_id
        album.updated_at = datetime.now(UTC)
        self._commit(prepared_shares)
        photo_count = self._session.scalar(
            select(func.count())
            .select_from(AlbumPhoto)
            .join(Photo, Photo.id == AlbumPhoto.photo_id)
            .where(
                AlbumPhoto.album_id == album_id,
                Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
            )
        )
        group_ids, group_names = self._group_details(album.id)
        fallback_cover_id = self._session.scalar(
            select(AlbumPhoto.photo_id)
            .join(Photo, Photo.id == AlbumPhoto.photo_id)
            .where(
                AlbumPhoto.album_id == album_id,
                Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
            )
            .order_by(
                case((AlbumPhoto.photo_id == album.cover_photo_id, 0), else_=1),
                AlbumPhoto.added_at,
                AlbumPhoto.photo_id,
            )
            .limit(1)
        )
        return self._summary(album, photo_count or 0, group_ids, group_names, fallback_cover_id)

    def delete_album(self, album_id: UUID, acting_user_id: UUID) -> None:
        album = self._get_album_model(album_id, acting_user_id, lock=True)
        self._session.delete(album)
        self._commit()

    def add_photos(
        self,
        album_id: UUID,
        photo_ids: list[UUID],
        acting_user_id: UUID,
        acting_username: str = "",
    ) -> AlbumDetail:
        album = self._get_album_model(album_id, acting_user_id, lock=True)
        requested_ids = set(photo_ids)
        group_ids = set(self._group_ids(album.id))
        prepared_shares = self._prepare_album_photo_sharing(
            album.id,
            group_ids,
            acting_user_id,
            requested_ids,
            acting_username,
        )

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
        self._commit(prepared_shares)
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
        statement = select(Album).where(Album.id == album_id, self._can_access(viewer_user_id))
        if lock:
            statement = statement.with_for_update()
        album = self._session.scalar(statement)
        if album is None:
            raise AlbumNotFoundError(album_id)
        if lock:
            group_ids = self._group_ids(album.id)
            if not group_ids or not (lock_user_group_ids(self._session, viewer_user_id, group_ids) & set(group_ids)):
                self._session.rollback()
                raise AlbumNotFoundError(album_id)
        return album

    def _commit(self, prepared_shares: PreparedAlbumPhotoShares | None = None) -> None:
        try:
            self._photo_sharing.commit(prepared_shares or PreparedAlbumPhotoShares(()))
        except AlbumPhotoSharingError as error:
            raise AlbumPersistenceError("Could not persist album changes") from error

    def _prepare_album_photo_sharing(
        self,
        album_id: UUID,
        group_ids: set[UUID],
        acting_user_id: UUID,
        candidate_photo_ids: set[UUID],
        acting_username: str,
    ) -> PreparedAlbumPhotoShares:
        if not candidate_photo_ids or not group_ids:
            return PreparedAlbumPhotoShares(())
        photos = self._photo_catalog.list_by_ids(candidate_photo_ids, acting_user_id)
        photos_by_id = {photo.id: photo for photo in photos}
        missing_photo_ids = candidate_photo_ids - photos_by_id.keys()
        if missing_photo_ids:
            raise PhotoNotFoundError(missing_photo_ids)
        owner_photo_group_ids: dict[UUID, set[UUID]] = {}
        unavailable_photo_ids: set[UUID] = set()
        for photo in photos:
            missing_group_ids = group_ids - {share.group_id for share in photo.shares}
            if not missing_group_ids:
                continue
            if photo.uploaded_by_user_id == acting_user_id:
                owner_photo_group_ids[photo.id] = missing_group_ids
            else:
                unavailable_photo_ids.add(photo.id)
        if unavailable_photo_ids:
            raise PhotoNotFoundError(unavailable_photo_ids)
        try:
            return self._photo_sharing.prepare_add_groups(owner_photo_group_ids, acting_user_id, acting_username)
        except AlbumPhotoSharingPermissionError as error:
            raise PhotoNotFoundError(set(owner_photo_group_ids)) from error
        except AlbumPhotoSharingError as error:
            raise AlbumPersistenceError("Could not prepare album photo sharing") from error

    def _group_ids(self, album_id: UUID) -> list[UUID]:
        return list(
            self._session.scalars(
                select(AlbumGroupShare.group_id)
                .where(AlbumGroupShare.album_id == album_id)
                .order_by(AlbumGroupShare.group_id)
            ).all()
        )

    def _album_photo_ids(self, album_id: UUID) -> list[UUID]:
        return list(self._session.scalars(select(AlbumPhoto.photo_id).where(AlbumPhoto.album_id == album_id)).all())

    def _group_details(self, album_id: UUID) -> tuple[list[UUID], list[str]]:
        rows = self._session.execute(
            select(AlbumGroupShare.group_id, FamilyGroup.name)
            .join(FamilyGroup, FamilyGroup.id == AlbumGroupShare.group_id)
            .where(AlbumGroupShare.album_id == album_id)
            .order_by(FamilyGroup.name.asc(), AlbumGroupShare.group_id.asc())
        ).all()
        return [group_id for group_id, _ in rows], [name for _, name in rows]

    @staticmethod
    def _summary(
        album: Album,
        photo_count: int,
        group_ids: list[UUID],
        group_names: list[str],
        cover_photo_id: UUID | None,
    ) -> AlbumSummary:
        return AlbumSummary(
            id=album.id,
            title=album.title,
            description=album.description,
            created_by_user_id=album.created_by_user_id,
            created_by_username=album.created_by_username,
            group_ids=group_ids,
            group_names=group_names,
            cover_photo_id=cover_photo_id,
            created_at=album.created_at,
            updated_at=album.updated_at,
            photo_count=photo_count,
        )

    @staticmethod
    def _can_access(viewer_user_id: UUID):
        return Album.id.in_(
            select(AlbumGroupShare.album_id)
            .join(FamilyGroupMember, FamilyGroupMember.group_id == AlbumGroupShare.group_id)
            .where(FamilyGroupMember.user_id == viewer_user_id)
        )

    @staticmethod
    def _encode_photo_cursor(sort_at: datetime, photo_id: UUID) -> str:
        payload = json.dumps(
            {"sort_at": sort_at.astimezone(UTC).isoformat(), "photo_id": str(photo_id)},
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_photo_cursor(value: str) -> tuple[datetime, UUID]:
        try:
            padding = "=" * (-len(value) % 4)
            payload = json.loads(base64.urlsafe_b64decode(value + padding))
            sort_at = datetime.fromisoformat(payload["sort_at"])
            photo_id = UUID(payload["photo_id"])
            if sort_at.tzinfo is None or sort_at.utcoffset() is None:
                raise ValueError
        except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise InvalidAlbumPhotoCursorError("Invalid album photo cursor") from error
        return sort_at.astimezone(UTC), photo_id
