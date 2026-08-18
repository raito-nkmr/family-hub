from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.features.albums.models import Album
from app.features.albums.public import clear_photo_as_cover


def test_clear_photo_as_cover_clears_cover_and_updates_album() -> None:
    session = MagicMock(spec=Session)
    photo_id = uuid4()
    album = Album(
        id=uuid4(),
        title="Family album",
        description=None,
        created_by_user_id=uuid4(),
        created_by_username="owner",
        group_id=uuid4(),
        cover_photo_id=photo_id,
    )
    session.scalars.return_value.all.return_value = [album]

    clear_photo_as_cover(session, photo_id)

    assert album.cover_photo_id is None
    assert album.updated_at is not None
    session.flush.assert_called_once_with()
