from datetime import UTC, datetime
from uuid import uuid4

from app.features.albums.models import Album


def make_album() -> Album:
    created_at = datetime(2026, 7, 14, 3, tzinfo=UTC)
    return Album(
        id=uuid4(),
        title="北海道旅行",
        description="2026年の家族旅行",
        created_by_user_id=uuid4(),
        created_by_username="owner",
        group_id=uuid4(),
        cover_photo_id=None,
        created_at=created_at,
        updated_at=created_at,
    )
