from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.features.albums.models import Album
from app.features.albums.public import album_is_visible_to_user, clear_photo_as_cover


def test_clear_photo_as_cover_clears_cover_and_updates_album() -> None:
    session = MagicMock(spec=Session)
    photo_id = uuid4()
    album = Album(
        id=uuid4(),
        title="Family album",
        description=None,
        created_by_user_id=uuid4(),
        created_by_username="owner",
        cover_photo_id=photo_id,
    )
    session.scalars.return_value.all.return_value = [album]

    clear_photo_as_cover(session, photo_id)

    assert album.cover_photo_id is None
    assert album.updated_at is not None
    session.flush.assert_called_once_with()


def test_album_visibility_uses_any_target_group_membership() -> None:
    statement = select(album_is_visible_to_user(uuid4(), uuid4()))
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "album_group_shares" in sql
    assert "family_group_members" in sql
    assert "albums.group_id" not in sql
