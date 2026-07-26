from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.features.albums.schemas import AlbumCreate, AlbumPhotoAdd, AlbumResponse, AlbumUpdate
from app.features.albums.service import AlbumSummary


def test_album_create_trims_text_and_normalizes_blank_description() -> None:
    body = AlbumCreate(title="  北海道旅行  ", description="   ", group_id=uuid4())

    assert body.title == "北海道旅行"
    assert body.description is None


def test_album_update_requires_a_field() -> None:
    with pytest.raises(ValidationError, match="at least one album field"):
        AlbumUpdate()


def test_album_update_rejects_null_title() -> None:
    with pytest.raises(ValidationError, match="album title must not be null"):
        AlbumUpdate(title=None)


def test_album_photo_add_rejects_duplicate_ids() -> None:
    photo_id = uuid4()

    with pytest.raises(ValidationError, match="must not contain duplicates"):
        AlbumPhotoAdd(photo_ids=[photo_id, photo_id])


def test_album_response_normalizes_datetimes_to_utc() -> None:
    jst = timezone(timedelta(hours=9))
    summary = AlbumSummary(
        id=uuid4(),
        title="北海道旅行",
        description=None,
        created_by_user_id=uuid4(),
        created_by_username="owner",
        group_id=uuid4(),
        group_name="同居家族",
        cover_photo_id=None,
        created_at=datetime(2026, 7, 14, 12, tzinfo=jst),
        updated_at=datetime(2026, 7, 14, 13, tzinfo=jst),
        photo_count=3,
    )

    response = AlbumResponse.model_validate(summary)

    assert response.created_at == datetime(2026, 7, 14, 3, tzinfo=UTC)
    assert response.updated_at == datetime(2026, 7, 14, 4, tzinfo=UTC)
