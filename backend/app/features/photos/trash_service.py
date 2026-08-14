import base64
import binascii
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.photos.models import Photo, PhotoDerivativeKind, PhotoFavorite, PhotoLifecycleState
from app.features.photos.registration import build_sidecar_metadata
from app.features.photos.service import (
    InvalidTrashCursorError,
    PhotoContent,
    PhotoContentUnavailableError,
    PhotoDeletePersistenceError,
    PhotoDeleteStorageError,
    PhotoNotFoundError,
    TrashedPhotoPage,
)
from app.features.photos.storage import PhotoStorage, PhotoStorageError, SidecarMetadata


class PhotoTrashService:
    """Owns trash transitions, permanent deletion, and retention purges."""

    def __init__(self, session: Session, storage: PhotoStorage, trash_retention_days: int = 30) -> None:
        self._session = session
        self._storage = storage
        self._trash_retention_days = trash_retention_days

    def list_trashed_photos(
        self,
        owner_user_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> TrashedPhotoPage:
        conditions = [
            Photo.uploaded_by_user_id == owner_user_id,
            Photo.lifecycle_state.in_((PhotoLifecycleState.TRASHED, PhotoLifecycleState.PURGE_PENDING)),
        ]
        total_count = self._session.scalar(select(func.count()).select_from(Photo).where(*conditions)) or 0
        if cursor:
            trashed_at, photo_id = self._decode_trash_cursor(cursor)
            conditions.append(
                or_(Photo.trashed_at < trashed_at, and_(Photo.trashed_at == trashed_at, Photo.id < photo_id))
            )
        rows = list(
            self._session.scalars(
                select(Photo).where(*conditions).order_by(Photo.trashed_at.desc(), Photo.id.desc()).limit(limit + 1)
            ).all()
        )
        has_more = len(rows) > limit
        items = rows[:limit]
        favorite_photo_ids = set(
            self._session.scalars(
                select(PhotoFavorite.photo_id).where(
                    PhotoFavorite.user_id == owner_user_id,
                    PhotoFavorite.photo_id.in_([photo.id for photo in items]),
                )
            ).all()
        )
        next_cursor = None
        if has_more and items:
            last = items[-1]
            if last.trashed_at is None:
                raise RuntimeError("Trashed photos must have trashed_at")
            next_cursor = self._encode_trash_cursor(last.trashed_at, last.id)
        return TrashedPhotoPage(items, favorite_photo_ids, next_cursor, total_count)

    def get_trashed_photo(self, photo_id: UUID, owner_user_id: UUID) -> Photo:
        photo = self._session.scalar(
            select(Photo).where(
                Photo.id == photo_id,
                Photo.uploaded_by_user_id == owner_user_id,
                Photo.lifecycle_state.in_((PhotoLifecycleState.TRASHED, PhotoLifecycleState.PURGE_PENDING)),
            )
        )
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        return photo

    def get_trashed_photo_thumbnail(self, photo_id: UUID, owner_user_id: UUID) -> PhotoContent:
        photo = self.get_trashed_photo(photo_id, owner_user_id)
        derivative = photo.get_derivative(PhotoDerivativeKind.THUMBNAIL)
        if derivative is None:
            raise PhotoContentUnavailableError(photo_id)
        try:
            path = self._storage.get_derivative_path(derivative.storage_key)
        except PhotoStorageError as error:
            raise PhotoContentUnavailableError(photo_id) from error
        return PhotoContent(path=path, content_type=derivative.content_type)

    def trash_photo(self, photo_id: UUID, owner_user_id: UUID) -> Photo:
        photo = self._lock_owned_photo(photo_id, owner_user_id, PhotoLifecycleState.ACTIVE)
        now = datetime.now(UTC)
        previous_metadata = build_sidecar_metadata(photo)
        photo.lifecycle_state = PhotoLifecycleState.TRASHED
        photo.trashed_at = now
        photo.trashed_by_user_id = owner_user_id
        photo.purge_after = now + timedelta(days=self._trash_retention_days)
        photo.purge_requested_at = None
        self._commit_lifecycle_change(photo, previous_metadata)
        return photo

    def restore_photo(self, photo_id: UUID, owner_user_id: UUID) -> Photo:
        photo = self._lock_owned_photo(photo_id, owner_user_id, PhotoLifecycleState.TRASHED)
        previous_metadata = build_sidecar_metadata(photo)
        photo.lifecycle_state = PhotoLifecycleState.ACTIVE
        photo.trashed_at = None
        photo.trashed_by_user_id = None
        photo.purge_after = None
        photo.purge_requested_at = None
        self._commit_lifecycle_change(photo, previous_metadata)
        return photo

    def permanently_delete_photo(self, photo_id: UUID, owner_user_id: UUID) -> None:
        photo = self._session.scalar(
            select(Photo)
            .where(
                Photo.id == photo_id,
                Photo.uploaded_by_user_id == owner_user_id,
                Photo.lifecycle_state.in_((PhotoLifecycleState.TRASHED, PhotoLifecycleState.PURGE_PENDING)),
            )
            .with_for_update()
        )
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        if photo.lifecycle_state == PhotoLifecycleState.TRASHED:
            previous_metadata = build_sidecar_metadata(photo)
            photo.lifecycle_state = PhotoLifecycleState.PURGE_PENDING
            photo.purge_requested_at = datetime.now(UTC)
            self._commit_lifecycle_change(photo, previous_metadata)
        self._delete_pending_photo(photo)

    def purge_due_photos(self, *, limit: int = 100) -> int:
        now = datetime.now(UTC)
        photo_ids = list(
            self._session.scalars(
                select(Photo.id)
                .where(
                    Photo.lifecycle_state.in_((PhotoLifecycleState.TRASHED, PhotoLifecycleState.PURGE_PENDING)),
                    Photo.purge_after <= now,
                )
                .order_by(Photo.purge_after, Photo.id)
                .limit(limit)
            ).all()
        )
        purged = 0
        for photo_id in photo_ids:
            photo = self._session.scalar(select(Photo).where(Photo.id == photo_id).with_for_update())
            if photo is None or photo.lifecycle_state == PhotoLifecycleState.ACTIVE:
                self._session.rollback()
                continue
            if photo.lifecycle_state == PhotoLifecycleState.TRASHED:
                previous_metadata = build_sidecar_metadata(photo)
                photo.lifecycle_state = PhotoLifecycleState.PURGE_PENDING
                photo.purge_requested_at = datetime.now(UTC)
                self._commit_lifecycle_change(photo, previous_metadata)
            self._delete_pending_photo(photo)
            purged += 1
        return purged

    def _lock_owned_photo(self, photo_id: UUID, owner_user_id: UUID, state: PhotoLifecycleState) -> Photo:
        photo = self._session.scalar(
            select(Photo)
            .where(
                Photo.id == photo_id,
                Photo.uploaded_by_user_id == owner_user_id,
                Photo.lifecycle_state == state,
            )
            .with_for_update()
        )
        if photo is None:
            raise PhotoNotFoundError(photo_id)
        return photo

    def _commit_lifecycle_change(self, photo: Photo, previous_metadata: SidecarMetadata) -> None:
        try:
            self._storage.update_sidecar(build_sidecar_metadata(photo))
        except PhotoStorageError as error:
            self._session.rollback()
            raise PhotoDeleteStorageError("Could not update photo lifecycle sidecar") from error
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            try:
                self._storage.update_sidecar(previous_metadata)
            except PhotoStorageError:
                pass
            raise PhotoDeletePersistenceError("Could not update photo lifecycle") from error

    def _delete_pending_photo(self, photo: Photo) -> None:
        derivative_keys = tuple(derivative.storage_key for derivative in photo.derivatives)
        try:
            self._storage.delete_photo_files(photo.storage_key, derivative_keys)
        except PhotoStorageError as error:
            self._session.rollback()
            raise PhotoDeleteStorageError("Could not permanently delete photo files") from error
        try:
            self._session.delete(photo)
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PhotoDeletePersistenceError("Could not remove permanently deleted photo record") from error

    @staticmethod
    def _encode_trash_cursor(trashed_at: datetime, photo_id: UUID) -> str:
        payload = json.dumps(
            {"trashed_at": trashed_at.astimezone(UTC).isoformat(), "photo_id": str(photo_id)},
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_trash_cursor(value: str) -> tuple[datetime, UUID]:
        try:
            padding = "=" * (-len(value) % 4)
            payload = json.loads(base64.urlsafe_b64decode(value + padding))
            trashed_at = datetime.fromisoformat(payload["trashed_at"])
            photo_id = UUID(payload["photo_id"])
            if trashed_at.tzinfo is None or trashed_at.utcoffset() is None:
                raise ValueError
        except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise InvalidTrashCursorError("Invalid trash cursor") from error
        return trashed_at.astimezone(UTC), photo_id
