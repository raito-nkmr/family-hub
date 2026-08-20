import base64
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.features.albums.models import Album, AlbumPhoto
from app.features.albums.public import remove_photo_from_group_albums
from app.features.albums.service import (
    AlbumNotFoundError,
    AlbumPersistenceError,
    AlbumService,
    InvalidAlbumPhotoCursorError,
    PhotoNotFoundError,
    PhotoNotInAlbumError,
)
from app.features.photos.public import PhotoCatalog
from tests.features.albums.factories import make_album
from tests.features.photos.factories import make_photo


def make_service(session: Session) -> tuple[AlbumService, MagicMock]:
    catalog = MagicMock(spec=PhotoCatalog)
    return AlbumService(session, catalog), catalog


def test_list_albums_returns_photo_counts_in_expected_order() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    session.execute.return_value.all.return_value = [(album, 2, "同居家族", None)]
    service, _ = make_service(session)

    result = service.list_albums(uuid4())

    assert result[0].id == album.id
    assert result[0].photo_count == 2
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY albums.updated_at DESC, albums.id DESC" in sql


def test_get_album_returns_photos_from_public_catalog() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    photo = make_photo()
    session.scalar.side_effect = [album, 1, "同居家族", photo.id]
    session.execute.return_value.all.return_value = [
        SimpleNamespace(photo_id=photo.id, effective_captured_at=datetime(2026, 7, 14, tzinfo=UTC))
    ]
    service, catalog = make_service(session)
    catalog.list_by_ids.return_value = [photo]
    catalog.favorite_photo_ids.return_value = {photo.id}
    user_id = uuid4()

    result = service.get_album(album.id, user_id)

    assert result.album.photo_count == 1
    assert result.photos == [photo]
    assert result.favorite_photo_ids == {photo.id}
    catalog.list_by_ids.assert_called_once_with([photo.id], user_id)
    catalog.favorite_photo_ids.assert_called_once_with([photo.id], user_id)


def test_get_album_raises_when_album_does_not_exist() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    service, _ = make_service(session)

    with pytest.raises(AlbumNotFoundError):
        service.get_album(uuid4(), uuid4())


def test_get_album_returns_bounded_photo_page_and_cursor() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    first = make_photo()
    second = make_photo()
    session.scalar.side_effect = [album, 2, "同居家族", first.id]
    session.execute.return_value.all.return_value = [
        SimpleNamespace(photo_id=first.id, effective_captured_at=datetime(2026, 7, 14, tzinfo=UTC)),
        SimpleNamespace(photo_id=second.id, effective_captured_at=datetime(2026, 7, 15, tzinfo=UTC)),
    ]
    service, catalog = make_service(session)
    catalog.list_by_ids.return_value = [first]

    result = service.get_album(album.id, uuid4(), limit=1)

    assert result.photos == [first]
    assert result.album.photo_count == 2
    assert result.next_cursor is not None
    sql = str(
        session.execute.call_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "photos.lifecycle_state = 'active'" in sql


def test_get_album_rejects_invalid_photo_cursor() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = make_album()
    service, _ = make_service(session)

    with pytest.raises(InvalidAlbumPhotoCursorError):
        service.get_album(uuid4(), uuid4(), cursor="not-a-cursor")


def test_album_photo_cursor_uses_effective_time_and_photo_id() -> None:
    sort_at = datetime(2026, 7, 14, tzinfo=UTC)
    photo_id = uuid4()

    cursor = AlbumService._encode_photo_cursor(sort_at, photo_id)

    assert AlbumService._decode_photo_cursor(cursor) == (sort_at, photo_id)
    with pytest.raises(InvalidAlbumPhotoCursorError):
        AlbumService._decode_photo_cursor(
            base64.urlsafe_b64encode(json.dumps({"added_at": sort_at.isoformat(), "photo_id": str(photo_id)}).encode())
            .decode()
            .rstrip("=")
        )


def test_create_album_records_creator_and_commits() -> None:
    session = MagicMock(spec=Session)
    service, _ = make_service(session)
    user_id = uuid4()
    group_id = uuid4()
    session.scalars.return_value.all.return_value = [group_id]
    session.scalar.return_value = "同居家族"

    result = service.create_album("北海道旅行", None, user_id, "owner", group_id)

    assert result.title == "北海道旅行"
    assert result.created_by_user_id == user_id
    assert result.photo_count == 0
    album = session.add.call_args.args[0]
    assert isinstance(album, Album)
    session.commit.assert_called_once_with()


def test_update_album_can_clear_description() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    session.scalar.side_effect = [album, album, 4, "同居家族", None]
    session.scalars.return_value.all.return_value = [album.group_id]
    service, _ = make_service(session)

    result = service.update_album(
        album.id,
        title=None,
        description=None,
        update_description=True,
        acting_user_id=uuid4(),
        cover_photo_id=None,
        update_cover=False,
    )

    assert album.description is None
    assert result.photo_count == 4
    session.commit.assert_called_once_with()


def test_update_album_sets_cover_from_album_photo() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    cover_photo_id = uuid4()
    session.scalar.side_effect = [album, album, cover_photo_id, 1, "同居家族", cover_photo_id]
    session.scalars.return_value.all.return_value = [album.group_id]
    session.get.return_value = AlbumPhoto(album_id=album.id, photo_id=cover_photo_id)
    service, _ = make_service(session)

    result = service.update_album(
        album.id,
        title=None,
        description=None,
        update_description=False,
        acting_user_id=uuid4(),
        cover_photo_id=cover_photo_id,
        update_cover=True,
    )

    assert album.cover_photo_id == cover_photo_id
    assert result.cover_photo_id == cover_photo_id
    assert "FOR UPDATE" in str(session.scalar.call_args_list[1].args[0])


def test_update_album_rejects_trashed_cover_photo() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    session.scalar.side_effect = [album, album, None]
    session.scalars.return_value.all.return_value = [album.group_id]
    service, _ = make_service(session)

    with pytest.raises(PhotoNotInAlbumError):
        service.update_album(
            album.id,
            title=None,
            description=None,
            update_description=False,
            acting_user_id=uuid4(),
            cover_photo_id=uuid4(),
            update_cover=True,
        )

    session.commit.assert_not_called()


def test_add_photos_rejects_missing_photos_before_mutation() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    existing_id = uuid4()
    missing_id = uuid4()
    session.scalar.side_effect = [album, album]
    session.scalars.return_value.all.return_value = [album.group_id]
    service, catalog = make_service(session)
    user_id = uuid4()
    catalog.get_addable_to_group_ids.return_value = {existing_id}

    with pytest.raises(PhotoNotFoundError) as error:
        service.add_photos(album.id, [existing_id, missing_id], user_id)

    assert error.value.photo_ids == {missing_id}
    catalog.get_addable_to_group_ids.assert_called_once_with({existing_id, missing_id}, album.group_id)
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_add_photos_only_registers_new_memberships() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    existing_id = uuid4()
    new_id = uuid4()
    session.scalar.side_effect = [album, album, album, 2, "同居家族", existing_id]
    session.scalars.return_value.all.side_effect = [
        [album.group_id],
        [existing_id],
    ]
    session.execute.return_value.all.return_value = [
        SimpleNamespace(photo_id=existing_id, effective_captured_at=datetime(2026, 7, 14, tzinfo=UTC)),
        SimpleNamespace(photo_id=new_id, effective_captured_at=datetime(2026, 7, 15, tzinfo=UTC)),
    ]
    service, catalog = make_service(session)
    catalog.get_addable_to_group_ids.return_value = {existing_id, new_id}
    catalog.list_by_ids.return_value = [make_photo()]

    service.add_photos(album.id, [existing_id, new_id], uuid4())

    membership = session.add.call_args.args[0]
    assert isinstance(membership, AlbumPhoto)
    assert membership.photo_id == new_id
    session.commit.assert_called_once_with()


def test_remove_photo_raises_when_membership_does_not_exist() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    session.scalar.side_effect = [album, album]
    session.scalars.return_value.all.return_value = [album.group_id]
    session.execute.return_value.rowcount = 0
    service, _ = make_service(session)

    with pytest.raises(PhotoNotInAlbumError):
        service.remove_photo(album.id, uuid4(), uuid4())

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_removed_sharing_also_removes_photo_from_group_albums() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    photo_id = uuid4()
    album.cover_photo_id = photo_id
    session.scalars.return_value.all.return_value = [album]

    remove_photo_from_group_albums(session, photo_id, {album.group_id})

    assert album.cover_photo_id is None
    session.flush.assert_called_once_with()
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "DELETE FROM album_photos" in sql
    assert "album_photos.photo_id" in sql


def test_persistence_failure_rolls_back() -> None:
    session = MagicMock(spec=Session)
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))
    service, _ = make_service(session)
    group_id = uuid4()
    session.scalars.return_value.all.return_value = [group_id]

    with pytest.raises(AlbumPersistenceError):
        service.create_album("北海道旅行", None, uuid4(), "owner", group_id)

    session.rollback.assert_called_once_with()
