from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.features.photos.models import PhotoVisibility
from app.features.photos.queries import (
    InvalidPhotoCursorError,
    PhotoAlbumNotFoundError,
    PhotoListFilters,
    PhotoQueryService,
)


def make_row(
    *, captured_at_original: datetime | None = None, visibility: str = "private", is_favorite: bool = False
) -> SimpleNamespace:
    uploaded_at = datetime(2026, 7, 14, 4, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid4(),
        uploaded_by_user_id=uuid4(),
        uploaded_by_username="owner",
        visibility=visibility,
        original_filename="IMG_0001.JPG",
        content_type="image/jpeg",
        width=4032,
        height=3024,
        captured_at_original=captured_at_original,
        captured_at_override=None,
        uploaded_at=uploaded_at,
        effective_captured_at=captured_at_original or uploaded_at,
        sort_at=captured_at_original or uploaded_at,
        is_favorite=is_favorite,
    )


def test_list_photos_returns_bounded_page_and_cursor() -> None:
    session = MagicMock(spec=Session)
    first = make_row(captured_at_original=datetime(2026, 7, 14, 3, tzinfo=UTC), visibility="shared")
    second = make_row(captured_at_original=datetime(2026, 7, 13, 3, tzinfo=UTC))
    session.scalar.return_value = 2
    session.execute.return_value.all.return_value = [first, second]
    service = PhotoQueryService(session, "Asia/Tokyo")

    page = service.list_photos(uuid4(), PhotoListFilters(limit=1))

    assert page.total_count == 2
    assert len(page.items) == 1
    assert page.items[0].id == first.id
    assert page.items[0].visibility is PhotoVisibility.SHARED
    assert page.next_cursor is not None
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY photos.effective_captured_at DESC" in sql
    assert "family_group_members" in sql


def test_list_photos_applies_cursor_and_search_filters() -> None:
    session = MagicMock(spec=Session)
    first = make_row(captured_at_original=datetime(2026, 7, 14, 3, tzinfo=UTC))
    second = make_row(captured_at_original=datetime(2026, 7, 13, 3, tzinfo=UTC))
    session.scalar.return_value = 2
    session.execute.return_value.all.side_effect = [[first, second], []]
    service = PhotoQueryService(session, "Asia/Tokyo")
    cursor = service.list_photos(uuid4(), PhotoListFilters(limit=1)).next_cursor

    service.list_photos(
        uuid4(),
        PhotoListFilters(
            cursor=cursor,
            keyword="旅行%",
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
            uploader_id=uuid4(),
            visibility=PhotoVisibility.PRIVATE,
            captured_at_known=True,
            exclude_album_id=uuid4(),
        ),
    )

    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "photo_metadata" in sql
    assert "photos.original_filename" in sql
    assert "photos.uploaded_by_user_id" in sql
    assert "coalesce(photo_metadata.captured_at_override, photos.captured_at_original) IS NOT NULL" in sql
    assert "album_photos" in sql
    assert "photos.effective_captured_at <" in sql


def test_list_photos_rejects_invalid_cursor() -> None:
    service = PhotoQueryService(MagicMock(spec=Session), "Asia/Tokyo")

    with pytest.raises(InvalidPhotoCursorError):
        service.list_photos(uuid4(), PhotoListFilters(cursor="not-a-cursor"))


def test_list_photos_hides_inaccessible_album_filters_as_not_found() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    service = PhotoQueryService(session, "Asia/Tokyo")
    album_id = uuid4()

    with pytest.raises(PhotoAlbumNotFoundError):
        service.list_photos(uuid4(), PhotoListFilters(album_id=album_id))

    session.execute.assert_not_called()


def test_search_options_returns_visible_uploaders_and_groups_in_stable_order() -> None:
    session = MagicMock(spec=Session)
    uploader_id = uuid4()
    group_id = uuid4()
    session.execute.return_value.all.side_effect = [
        [(uploader_id, "Alice")],
        [(group_id, "Family")],
    ]
    service = PhotoQueryService(session, "Asia/Tokyo")

    result = service.search_options(uuid4())

    assert [(item.id, item.label) for item in result.uploaders] == [(uploader_id, "Alice")]
    assert [(item.id, item.label) for item in result.groups] == [(group_id, "Family")]
    uploader_sql = str(
        session.execute.call_args_list[0]
        .args[0]
        .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    group_sql = str(session.execute.call_args_list[1].args[0].compile(dialect=postgresql.dialect()))
    assert "photos.lifecycle_state = 'active'" in uploader_sql
    assert "ORDER BY photos.uploaded_by_username ASC, photos.uploaded_by_user_id ASC" in uploader_sql
    assert "ORDER BY family_groups.name ASC, family_groups.id ASC" in group_sql


def test_timeline_groups_photos_by_jst_month() -> None:
    session = MagicMock(spec=Session)
    session.execute.return_value.__iter__.return_value = iter([SimpleNamespace(month=datetime(2026, 7, 1), count=12)])
    service = PhotoQueryService(session, "Asia/Tokyo")

    months = service.timeline(uuid4(), 2026)

    assert [(month.month, month.count) for month in months] == [("2026-07", 12)]
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "date_trunc" in sql
    assert "timezone" in sql
