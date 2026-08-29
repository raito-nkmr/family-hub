from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.features.photos.activity import InvalidPhotoActivityCursorError, PhotoActivityService
from app.features.photos.models import PhotoActivityEvent, PhotoActivityEventType


def make_row(*, occurred_at: datetime | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        event_type=PhotoActivityEventType.UPLOADED,
        actor_user_id=uuid4(),
        actor_username="family",
        activity_operation_id=uuid4(),
        occurred_at=occurred_at or datetime(2026, 7, 16, 3, tzinfo=UTC),
        photo_id=uuid4(),
        uploaded_by_user_id=uuid4(),
        uploaded_by_username="family",
        original_filename="new.jpg",
        content_type="image/jpeg",
        width=640,
        height=480,
        captured_at_original=None,
        captured_at_override=None,
        uploaded_at=datetime(2026, 7, 16, 3, tzinfo=UTC),
        effective_captured_at=datetime(2026, 7, 16, 3, tzinfo=UTC),
        is_favorite=False,
    )


def test_list_activity_filters_by_current_sharing_and_membership() -> None:
    session = MagicMock(spec=Session)
    first = make_row()
    second = make_row(occurred_at=datetime(2026, 7, 15, 3, tzinfo=UTC))
    session.execute.return_value.all.return_value = [first, second]
    session.get.return_value = None
    session.scalar.return_value = 2
    viewer_id = uuid4()

    page = PhotoActivityService(session).list_activity(viewer_id, limit=1)

    assert len(page.items) == 1
    assert page.items[0].id == first.id
    assert page.items[0].photo.id == first.photo_id
    assert page.next_cursor is not None
    assert page.unseen_count == 2
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "photo_activity_event_groups" in sql
    assert "family_group_members.joined_at <= photo_activity_events.occurred_at" in sql
    assert "photo_shares" in sql
    assert "photo_activity_events.actor_user_id !=" in sql


def test_list_activity_rejects_invalid_cursor() -> None:
    with pytest.raises(InvalidPhotoActivityCursorError):
        PhotoActivityService(MagicMock(spec=Session)).list_activity(uuid4(), cursor="invalid")


def test_mark_seen_stores_exact_event_position() -> None:
    session = MagicMock(spec=Session)
    event = PhotoActivityEvent(
        id=uuid4(),
        photo_id=uuid4(),
        actor_user_id=uuid4(),
        actor_username="family",
        event_type=PhotoActivityEventType.UPLOADED,
        activity_operation_id=uuid4(),
        occurred_at=datetime(2026, 7, 16, 3, tzinfo=UTC),
        groups=[],
    )
    session.scalar.return_value = event
    viewer_id = uuid4()

    PhotoActivityService(session).mark_seen(viewer_id, event.id)

    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (user_id) DO UPDATE" in sql
    assert "excluded.seen_through_at" in sql
    compiled = statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    assert str(viewer_id) in str(compiled)
    session.commit.assert_called_once_with()
