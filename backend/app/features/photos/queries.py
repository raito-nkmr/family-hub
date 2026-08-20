import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, exists, func, not_, or_, select
from sqlalchemy.orm import Session

from app.features.albums.public import Album, album_is_visible_to_user, photo_is_in_album
from app.features.groups.public import FamilyGroup, FamilyGroupMember
from app.features.photos.access import photo_is_in_library, photo_is_shared
from app.features.photos.models import Photo, PhotoFavorite, PhotoMetadata, PhotoShare, PhotoVisibility


class InvalidPhotoCursorError(ValueError):
    pass


class PhotoAlbumNotFoundError(ValueError):
    def __init__(self, album_id: UUID) -> None:
        super().__init__(f"Album {album_id} was not found")
        self.album_id = album_id


@dataclass(frozen=True, slots=True)
class PhotoListFilters:
    limit: int = 50
    cursor: str | None = None
    keyword: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    uploader_id: UUID | None = None
    visibility: PhotoVisibility | None = None
    captured_at_known: bool | None = None
    album_id: UUID | None = None
    exclude_album_id: UUID | None = None
    sharing_group_id: UUID | None = None
    favorite: bool | None = None


@dataclass(frozen=True, slots=True)
class PhotoListItem:
    id: UUID
    uploaded_by_user_id: UUID
    uploaded_by_username: str
    visibility: PhotoVisibility
    original_filename: str
    content_type: str
    width: int
    height: int
    captured_at: datetime | None
    uploaded_at: datetime
    is_favorite: bool


@dataclass(frozen=True, slots=True)
class PhotoListPage:
    items: list[PhotoListItem]
    next_cursor: str | None
    total_count: int


@dataclass(frozen=True, slots=True)
class PhotoTimelineMonth:
    month: str
    count: int


@dataclass(frozen=True, slots=True)
class PhotoSearchOption:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class PhotoSearchOptions:
    uploaders: list[PhotoSearchOption]
    groups: list[PhotoSearchOption]


@dataclass(frozen=True, slots=True)
class _PhotoCursor:
    sort_at: datetime
    photo_id: UUID


class PhotoQueryService:
    def __init__(self, session: Session, default_timezone: str) -> None:
        self._session = session
        self._timezone = ZoneInfo(default_timezone)

    def list_photos(self, viewer_user_id: UUID, filters: PhotoListFilters) -> PhotoListPage:
        self._validate_album_filter(viewer_user_id, filters)
        sort_at = Photo.effective_captured_at
        shared_condition = photo_is_shared()
        favorite = exists(
            select(PhotoFavorite.photo_id).where(
                PhotoFavorite.photo_id == Photo.id,
                PhotoFavorite.user_id == viewer_user_id,
            )
        )
        conditions = self._conditions(viewer_user_id, filters, sort_at, shared_condition)
        total_count = (
            self._session.scalar(
                select(func.count())
                .select_from(Photo)
                .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
                .where(*conditions)
            )
            or 0
        )

        cursor = self._decode_cursor(filters.cursor) if filters.cursor else None
        page_conditions = list(conditions)
        if cursor is not None:
            page_conditions.append(
                or_(
                    sort_at < cursor.sort_at,
                    and_(sort_at == cursor.sort_at, Photo.id < cursor.photo_id),
                )
            )

        statement = (
            select(
                Photo.id,
                Photo.uploaded_by_user_id,
                Photo.uploaded_by_username,
                case((shared_condition, PhotoVisibility.SHARED.value), else_=PhotoVisibility.PRIVATE.value).label(
                    "visibility"
                ),
                Photo.original_filename,
                Photo.content_type,
                Photo.width,
                Photo.height,
                func.coalesce(PhotoMetadata.captured_at_override, Photo.captured_at).label("captured_at"),
                Photo.uploaded_at,
                sort_at.label("sort_at"),
                favorite.label("is_favorite"),
            )
            .where(*page_conditions)
            .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
            .order_by(sort_at.desc(), Photo.id.desc())
            .limit(filters.limit + 1)
        )
        rows = self._session.execute(statement).all()
        has_more = len(rows) > filters.limit
        page_rows = rows[: filters.limit]
        items = [
            PhotoListItem(
                id=row.id,
                uploaded_by_user_id=row.uploaded_by_user_id,
                uploaded_by_username=row.uploaded_by_username,
                visibility=PhotoVisibility(row.visibility),
                original_filename=row.original_filename,
                content_type=row.content_type,
                width=row.width,
                height=row.height,
                captured_at=row.captured_at,
                uploaded_at=row.uploaded_at,
                is_favorite=row.is_favorite,
            )
            for row in page_rows
        ]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = self._encode_cursor(_PhotoCursor(sort_at=last.sort_at, photo_id=last.id))
        return PhotoListPage(items=items, next_cursor=next_cursor, total_count=total_count)

    def search_options(self, viewer_user_id: UUID) -> PhotoSearchOptions:
        uploader_rows = self._session.execute(
            select(Photo.uploaded_by_user_id, Photo.uploaded_by_username)
            .where(photo_is_in_library(viewer_user_id))
            .distinct()
            .order_by(Photo.uploaded_by_username.asc(), Photo.uploaded_by_user_id.asc())
        ).all()
        group_rows = self._session.execute(
            select(FamilyGroup.id, FamilyGroup.name)
            .join(FamilyGroupMember, FamilyGroupMember.group_id == FamilyGroup.id)
            .where(FamilyGroupMember.user_id == viewer_user_id)
            .order_by(FamilyGroup.name.asc(), FamilyGroup.id.asc())
        ).all()
        return PhotoSearchOptions(
            uploaders=[PhotoSearchOption(id=user_id, name=username) for user_id, username in uploader_rows],
            groups=[PhotoSearchOption(id=group_id, name=name) for group_id, name in group_rows],
        )

    def timeline(self, viewer_user_id: UUID, year: int) -> list[PhotoTimelineMonth]:
        start = datetime.combine(date(year, 1, 1), time.min, self._timezone).astimezone(UTC)
        end = datetime.combine(date(year + 1, 1, 1), time.min, self._timezone).astimezone(UTC)
        sort_at = Photo.effective_captured_at
        local_month = func.date_trunc("month", func.timezone(str(self._timezone), sort_at))
        statement = (
            select(local_month.label("month"), func.count().label("count"))
            .select_from(Photo)
            .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
            .where(photo_is_in_library(viewer_user_id), sort_at >= start, sort_at < end)
            .group_by(local_month)
            .order_by(local_month.desc())
        )
        return [
            PhotoTimelineMonth(month=row.month.strftime("%Y-%m"), count=row.count)
            for row in self._session.execute(statement)
        ]

    def _conditions(self, viewer_user_id: UUID, filters: PhotoListFilters, sort_at, shared_condition) -> list:
        conditions = [photo_is_in_library(viewer_user_id)]
        if filters.keyword:
            escaped = self._escape_like(filters.keyword.strip())
            pattern = f"%{escaped}%"
            conditions.append(
                or_(
                    Photo.original_filename.ilike(pattern, escape="\\"),
                    Photo.id.in_(select(PhotoMetadata.photo_id).where(PhotoMetadata.memo.ilike(pattern, escape="\\"))),
                )
            )
        if filters.date_from:
            conditions.append(sort_at >= self._start_of_day(filters.date_from))
        if filters.date_to:
            conditions.append(sort_at < self._start_of_day(filters.date_to + timedelta(days=1)))
        if filters.uploader_id:
            conditions.append(Photo.uploaded_by_user_id == filters.uploader_id)
        if filters.visibility is PhotoVisibility.SHARED:
            conditions.append(shared_condition)
        elif filters.visibility is PhotoVisibility.PRIVATE:
            conditions.append(not_(shared_condition))
        captured_at = func.coalesce(PhotoMetadata.captured_at_override, Photo.captured_at)
        if filters.captured_at_known is True:
            conditions.append(captured_at.is_not(None))
        elif filters.captured_at_known is False:
            conditions.append(captured_at.is_(None))
        if filters.sharing_group_id:
            conditions.append(
                and_(
                    exists(
                        select(FamilyGroupMember.group_id).where(
                            FamilyGroupMember.group_id == filters.sharing_group_id,
                            FamilyGroupMember.user_id == viewer_user_id,
                        )
                    ),
                    exists(
                        select(PhotoShare.id).where(
                            PhotoShare.photo_id == Photo.id,
                            PhotoShare.group_id == filters.sharing_group_id,
                        )
                    ),
                )
            )
        if filters.favorite is not None:
            favorite_exists = exists(
                select(PhotoFavorite.photo_id).where(
                    PhotoFavorite.photo_id == Photo.id,
                    PhotoFavorite.user_id == viewer_user_id,
                )
            )
            conditions.append(favorite_exists if filters.favorite else not_(favorite_exists))
        if filters.album_id:
            conditions.extend(
                [
                    album_is_visible_to_user(filters.album_id, viewer_user_id),
                    photo_is_in_album(Photo.id, filters.album_id),
                ]
            )
        elif filters.exclude_album_id:
            conditions.extend(
                [
                    album_is_visible_to_user(filters.exclude_album_id, viewer_user_id),
                    not_(photo_is_in_album(Photo.id, filters.exclude_album_id)),
                ]
            )
        return conditions

    def _validate_album_filter(self, viewer_user_id: UUID, filters: PhotoListFilters) -> None:
        album_id = filters.album_id or filters.exclude_album_id
        if album_id is None:
            return
        if self._session.scalar(select(Album.id).where(album_is_visible_to_user(album_id, viewer_user_id))) is None:
            raise PhotoAlbumNotFoundError(album_id)

    def _start_of_day(self, value: date) -> datetime:
        return datetime.combine(value, time.min, self._timezone).astimezone(UTC)

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _encode_cursor(cursor: _PhotoCursor) -> str:
        payload = json.dumps(
            {"sort_at": cursor.sort_at.astimezone(UTC).isoformat(), "id": str(cursor.photo_id)},
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(value: str) -> _PhotoCursor:
        try:
            padding = "=" * (-len(value) % 4)
            payload = json.loads(base64.urlsafe_b64decode(value + padding))
            sort_at = datetime.fromisoformat(payload["sort_at"])
            photo_id = UUID(payload["id"])
            if sort_at.tzinfo is None or sort_at.utcoffset() is None:
                raise ValueError
        except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise InvalidPhotoCursorError("Invalid photo cursor") from error
        return _PhotoCursor(sort_at=sort_at.astimezone(UTC), photo_id=photo_id)
