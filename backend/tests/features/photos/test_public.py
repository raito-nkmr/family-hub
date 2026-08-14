from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.features.photos.models import PhotoVisibility
from app.features.photos.public import PhotoCatalog
from tests.features.photos.factories import make_photo


def test_photo_catalog_lists_album_photos_oldest_first() -> None:
    session = MagicMock(spec=Session)
    photos = [make_photo(), make_photo()]
    session.scalars.return_value.all.return_value = photos
    catalog = PhotoCatalog(session)

    viewer_user_id = photos[0].uploaded_by_user_id
    result = catalog.list_by_ids([photo.id for photo in photos], viewer_user_id)

    assert result == photos
    statement = session.scalars.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY coalesce(photo_metadata.captured_at_override, photos.captured_at, photos.uploaded_at) ASC" in sql
    assert "family_group_members.user_id" in sql


def test_photo_catalog_returns_photos_shared_with_group() -> None:
    session = MagicMock(spec=Session)
    photo = make_photo(visibility=PhotoVisibility.SHARED)
    session.scalars.return_value.all.return_value = [photo.id]
    catalog = PhotoCatalog(session)

    group_id = photo.shares[0].group_id

    assert catalog.get_addable_to_group_ids({photo.id}, group_id) == {photo.id}
    statement = session.scalars.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "photo_shares" in sql
    assert "photos.lifecycle_state = 'active'" in sql
