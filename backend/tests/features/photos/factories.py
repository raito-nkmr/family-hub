from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.features.photos.models import (
    Photo,
    PhotoDerivative,
    PhotoDerivativeKind,
    PhotoLifecycleState,
    PhotoMetadata,
    PhotoShare,
    PhotoVisibility,
)


def make_photo(
    photo_id: UUID | None = None,
    *,
    uploaded_by_user_id: UUID | None = None,
    uploaded_by_username: str = "owner",
    visibility: PhotoVisibility = PhotoVisibility.PRIVATE,
    group_id: UUID | None = None,
) -> Photo:
    resolved_photo_id = photo_id or uuid4()
    resolved_uploader_id = uploaded_by_user_id or uuid4()
    uploaded_at = datetime(2026, 7, 14, 4, tzinfo=UTC)
    return Photo(
        id=resolved_photo_id,
        uploaded_by_user_id=resolved_uploader_id,
        uploaded_by_username=uploaded_by_username,
        original_filename="photo.jpg",
        storage_key="originals/2026/07/photo.jpg",
        content_type="image/jpeg",
        size_bytes=1_024,
        sha256="a" * 64,
        width=640,
        height=480,
        captured_at=datetime(2026, 7, 14, 3, tzinfo=UTC),
        uploaded_at=uploaded_at,
        effective_captured_at=datetime(2026, 7, 14, 3, tzinfo=UTC),
        lifecycle_state=PhotoLifecycleState.ACTIVE,
        trashed_at=None,
        trashed_by_user_id=None,
        purge_after=None,
        purge_requested_at=None,
        derivatives=[
            PhotoDerivative(
                id=uuid4(),
                photo_id=resolved_photo_id,
                kind=PhotoDerivativeKind.THUMBNAIL,
                storage_key=f"thumbnails/2026/07/{resolved_photo_id}.webp",
                content_type="image/webp",
                width=480,
                height=360,
                size_bytes=32_768,
                created_at=uploaded_at,
            )
        ],
        metadata_record=PhotoMetadata(
            photo_id=resolved_photo_id,
            memo=None,
            memo_updated_by_user_id=resolved_uploader_id,
            memo_updated_by_username=uploaded_by_username,
            memo_updated_at=uploaded_at,
            captured_at_override=None,
            version=1,
            created_at=uploaded_at,
            updated_at=uploaded_at,
        ),
        shares=(
            [
                PhotoShare(
                    id=uuid4(),
                    photo_id=resolved_photo_id,
                    group_id=group_id or uuid4(),
                    created_at=uploaded_at,
                )
            ]
            if visibility is PhotoVisibility.SHARED
            else []
        ),
    )
