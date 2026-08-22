import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.groups.public import FamilyGroupMember
from app.features.photos.models import (
    Photo,
    PhotoActivityEvent,
    PhotoActivityEventGroup,
    PhotoActivityEventType,
    PhotoActivityState,
    PhotoFavorite,
    PhotoLifecycleState,
    PhotoMetadata,
    PhotoShare,
    PhotoVisibility,
)
from app.features.photos.queries import PhotoListItem


class InvalidPhotoActivityCursorError(ValueError):
    pass


class PhotoActivityNotFoundError(Exception):
    pass


class PhotoActivityPersistenceError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PhotoActivityItem:
    id: UUID
    event_type: PhotoActivityEventType
    actor_user_id: UUID
    actor_username: str
    activity_operation_id: UUID
    occurred_at: datetime
    photo: PhotoListItem


@dataclass(frozen=True, slots=True)
class PhotoActivityPage:
    items: list[PhotoActivityItem]
    next_cursor: str | None
    unseen_count: int


@dataclass(frozen=True, slots=True)
class _ActivityCursor:
    occurred_at: datetime
    event_id: UUID


class PhotoActivityService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_activity(
        self,
        viewer_user_id: UUID,
        *,
        limit: int = 30,
        cursor: str | None = None,
    ) -> PhotoActivityPage:
        visible = self._is_visible(viewer_user_id)
        conditions = [PhotoActivityEvent.actor_user_id != viewer_user_id, visible]
        decoded_cursor = self._decode_cursor(cursor) if cursor else None
        if decoded_cursor is not None:
            conditions.append(
                or_(
                    PhotoActivityEvent.occurred_at < decoded_cursor.occurred_at,
                    and_(
                        PhotoActivityEvent.occurred_at == decoded_cursor.occurred_at,
                        PhotoActivityEvent.id < decoded_cursor.event_id,
                    ),
                )
            )
        favorite = exists(
            select(PhotoFavorite.photo_id).where(
                PhotoFavorite.photo_id == Photo.id,
                PhotoFavorite.user_id == viewer_user_id,
            )
        )
        statement = (
            select(
                PhotoActivityEvent.id,
                PhotoActivityEvent.event_type,
                PhotoActivityEvent.actor_user_id,
                PhotoActivityEvent.actor_username,
                PhotoActivityEvent.activity_operation_id,
                PhotoActivityEvent.occurred_at,
                Photo.id.label("photo_id"),
                Photo.uploaded_by_user_id,
                Photo.uploaded_by_username,
                Photo.original_filename,
                Photo.content_type,
                Photo.width,
                Photo.height,
                Photo.captured_at_original,
                PhotoMetadata.captured_at_override,
                Photo.uploaded_at,
                Photo.effective_captured_at.label("effective_captured_at"),
                favorite.label("is_favorite"),
            )
            .join(Photo, Photo.id == PhotoActivityEvent.photo_id)
            .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
            .where(*conditions)
            .order_by(PhotoActivityEvent.occurred_at.desc(), PhotoActivityEvent.id.desc())
            .limit(limit + 1)
        )
        rows = self._session.execute(statement).all()
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items = [
            PhotoActivityItem(
                id=row.id,
                event_type=PhotoActivityEventType(row.event_type),
                actor_user_id=row.actor_user_id,
                actor_username=row.actor_username,
                activity_operation_id=row.activity_operation_id,
                occurred_at=row.occurred_at,
                photo=PhotoListItem(
                    id=row.photo_id,
                    uploaded_by_user_id=row.uploaded_by_user_id,
                    uploaded_by_username=row.uploaded_by_username,
                    visibility=PhotoVisibility.SHARED,
                    original_filename=row.original_filename,
                    content_type=row.content_type,
                    width=row.width,
                    height=row.height,
                    captured_at_original=row.captured_at_original,
                    captured_at_override=row.captured_at_override,
                    uploaded_at=row.uploaded_at,
                    effective_captured_at=row.effective_captured_at,
                    is_favorite=row.is_favorite,
                ),
            )
            for row in page_rows
        ]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = self._encode_cursor(_ActivityCursor(last.occurred_at, last.id))
        return PhotoActivityPage(
            items=items,
            next_cursor=next_cursor,
            unseen_count=self._unseen_count(viewer_user_id, visible),
        )

    def mark_seen(self, viewer_user_id: UUID, event_id: UUID) -> None:
        event = self._session.scalar(
            select(PhotoActivityEvent).where(
                PhotoActivityEvent.id == event_id,
                PhotoActivityEvent.actor_user_id != viewer_user_id,
                self._is_visible(viewer_user_id),
            )
        )
        if event is None:
            raise PhotoActivityNotFoundError
        statement = insert(PhotoActivityState).values(
            user_id=viewer_user_id,
            seen_through_at=event.occurred_at,
            seen_through_event_id=event.id,
        )
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            index_elements=[PhotoActivityState.user_id],
            set_={
                "seen_through_at": excluded.seen_through_at,
                "seen_through_event_id": excluded.seen_through_event_id,
            },
            where=tuple_(excluded.seen_through_at, excluded.seen_through_event_id)
            > tuple_(PhotoActivityState.seen_through_at, PhotoActivityState.seen_through_event_id),
        )
        try:
            self._session.execute(statement)
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PhotoActivityPersistenceError from error

    def _unseen_count(self, viewer_user_id: UUID, visible) -> int:
        state = self._session.get(PhotoActivityState, viewer_user_id)
        conditions = [PhotoActivityEvent.actor_user_id != viewer_user_id, visible]
        if state is not None:
            conditions.append(
                or_(
                    PhotoActivityEvent.occurred_at > state.seen_through_at,
                    and_(
                        PhotoActivityEvent.occurred_at == state.seen_through_at,
                        PhotoActivityEvent.id > state.seen_through_event_id,
                    ),
                )
            )
        return self._session.scalar(select(func.count()).select_from(PhotoActivityEvent).where(*conditions)) or 0

    @staticmethod
    def _is_visible(viewer_user_id: UUID):
        return and_(
            exists(
                select(Photo.id)
                .where(
                    Photo.id == PhotoActivityEvent.photo_id,
                    Photo.lifecycle_state == PhotoLifecycleState.ACTIVE,
                )
                .correlate(PhotoActivityEvent)
            ),
            exists(
                select(PhotoActivityEventGroup.event_id)
                .join(FamilyGroupMember, FamilyGroupMember.group_id == PhotoActivityEventGroup.group_id)
                .join(
                    PhotoShare,
                    and_(
                        PhotoShare.photo_id == PhotoActivityEvent.photo_id,
                        PhotoShare.group_id == PhotoActivityEventGroup.group_id,
                    ),
                )
                .where(
                    PhotoActivityEventGroup.event_id == PhotoActivityEvent.id,
                    FamilyGroupMember.user_id == viewer_user_id,
                    FamilyGroupMember.joined_at <= PhotoActivityEvent.occurred_at,
                )
            ),
        )

    @staticmethod
    def _encode_cursor(cursor: _ActivityCursor) -> str:
        payload = json.dumps(
            {"occurred_at": cursor.occurred_at.astimezone(UTC).isoformat(), "id": str(cursor.event_id)},
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(value: str) -> _ActivityCursor:
        try:
            padding = "=" * (-len(value) % 4)
            payload = json.loads(base64.urlsafe_b64decode(value + padding))
            occurred_at = datetime.fromisoformat(payload["occurred_at"])
            event_id = UUID(payload["id"])
            if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
                raise ValueError
        except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise InvalidPhotoActivityCursorError("Invalid photo activity cursor") from error
        return _ActivityCursor(occurred_at.astimezone(UTC), event_id)
