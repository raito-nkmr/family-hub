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

from app.features.albums.models import AlbumGroupShare, AlbumPhoto
from app.features.albums.public import remove_photo_from_all_albums
from app.features.albums.service import (
    AlbumDetail,
    AlbumNotFoundError,
    AlbumPersistenceError,
    AlbumService,
    InvalidAlbumPhotoCursorError,
    PhotoNotFoundError,
    PhotoNotInAlbumError,
)
from app.features.photos.album_sharing import AlbumPhotoSharingError, PhotoAlbumSharingService, PreparedAlbumPhotoShares
from app.features.photos.models import PhotoVisibility
from app.features.photos.public import PhotoCatalog
from tests.features.albums.factories import make_album
from tests.features.photos.factories import make_photo


def make_service(session: Session) -> tuple[AlbumService, MagicMock, MagicMock]:
    catalog = MagicMock(spec=PhotoCatalog)
    photo_sharing = MagicMock(spec=PhotoAlbumSharingService)
    photo_sharing.commit.side_effect = lambda _prepared: session.commit()
    return AlbumService(session, catalog, photo_sharing), catalog, photo_sharing


def test_list_albums_returns_photo_counts_in_expected_order() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    group_id = uuid4()
    second_group_id = uuid4()
    session.execute.side_effect = [
        SimpleNamespace(all=lambda: [(album, 2, None)]),
        SimpleNamespace(all=lambda: [(group_id, "同居家族"), (second_group_id, "親族")]),
    ]
    service, _, _ = make_service(session)

    result = service.list_albums(uuid4())

    assert result[0].photo_count == 2
    assert result[0].group_ids == [group_id, second_group_id]
    assert result[0].group_names == ["同居家族", "親族"]
    statement = session.execute.call_args_list[0].args[0]
    assert "ORDER BY albums.updated_at DESC, albums.id DESC" in str(statement.compile(dialect=postgresql.dialect()))
    group_statement = session.execute.call_args_list[1].args[0]
    assert "ORDER BY family_groups.name ASC, album_group_shares.group_id ASC" in str(
        group_statement.compile(dialect=postgresql.dialect())
    )


def test_get_album_returns_photos_and_group_details_from_public_catalog() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    photo = make_photo()
    group_id = uuid4()
    session.scalar.side_effect = [album, 1, photo.id]
    session.execute.side_effect = [
        SimpleNamespace(
            all=lambda: [SimpleNamespace(photo_id=photo.id, effective_captured_at=datetime(2026, 7, 14, tzinfo=UTC))]
        ),
        SimpleNamespace(all=lambda: [(group_id, "同居家族")]),
    ]
    service, catalog, _ = make_service(session)
    catalog.list_by_ids.return_value = [photo]
    catalog.favorite_photo_ids.return_value = {photo.id}

    result = service.get_album(album.id, uuid4())

    assert result.photos == [photo]
    assert result.album.group_ids == [group_id]
    assert result.favorite_photo_ids == {photo.id}


def test_get_album_raises_when_album_does_not_exist() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    service, _, _ = make_service(session)

    with pytest.raises(AlbumNotFoundError):
        service.get_album(uuid4(), uuid4())


def test_album_mutation_locks_groups_before_album() -> None:
    session = MagicMock(spec=Session)
    service, _, _ = make_service(session)
    album = make_album()
    group_id = uuid4()
    session.scalars.side_effect = [
        SimpleNamespace(all=lambda: [group_id]),
        SimpleNamespace(all=lambda: [group_id]),
        SimpleNamespace(all=lambda: [group_id]),
        SimpleNamespace(all=lambda: [group_id]),
    ]
    session.scalar.return_value = album

    result = service._get_album_model(album.id, uuid4(), lock=True)

    assert result is album
    group_lock_sql = str(session.scalars.call_args_list[1].args[0].compile(dialect=postgresql.dialect()))
    album_lock_sql = str(session.scalar.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF family_groups" in group_lock_sql
    assert "FOR UPDATE" in album_lock_sql
    assert session.method_calls[-1][0] == "scalar"


def test_album_group_update_locks_added_groups_before_album() -> None:
    session = MagicMock(spec=Session)
    service, _, _ = make_service(session)
    album = make_album()
    current_group_id = uuid4()
    added_group_id = uuid4()
    session.scalars.side_effect = [
        SimpleNamespace(all=lambda: [current_group_id]),
        SimpleNamespace(all=lambda: [current_group_id, added_group_id]),
        SimpleNamespace(all=lambda: [current_group_id, added_group_id]),
        SimpleNamespace(all=lambda: [current_group_id]),
    ]
    session.scalar.return_value = album

    result = service._get_album_model(
        album.id,
        uuid4(),
        lock=True,
        requested_group_ids={current_group_id, added_group_id},
    )

    assert result is album
    assert session.method_calls[-1][0] == "scalar"


def test_get_album_returns_bounded_photo_page_and_cursor() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    first = make_photo()
    second = make_photo()
    session.scalar.side_effect = [album, 2, None]
    session.execute.side_effect = [
        SimpleNamespace(
            all=lambda: [
                SimpleNamespace(photo_id=first.id, effective_captured_at=datetime(2026, 7, 14, tzinfo=UTC)),
                SimpleNamespace(photo_id=second.id, effective_captured_at=datetime(2026, 7, 15, tzinfo=UTC)),
            ]
        ),
        SimpleNamespace(all=lambda: []),
    ]
    service, catalog, _ = make_service(session)
    catalog.list_by_ids.return_value = [first]

    result = service.get_album(album.id, uuid4(), limit=1)

    assert result.photos == [first]
    assert result.album.photo_count == 2
    assert result.next_cursor is not None
    sql = str(
        session.execute.call_args_list[0]
        .args[0]
        .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "photos.lifecycle_state = 'active'" in sql


def test_get_album_rejects_invalid_photo_cursor() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = make_album()
    service, _, _ = make_service(session)

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


def test_create_album_records_all_group_shares() -> None:
    session = MagicMock(spec=Session)
    service, _, _ = make_service(session)
    user_id = uuid4()
    group_ids = [uuid4(), uuid4()]
    session.scalars.return_value.all.return_value = group_ids
    service._group_details = MagicMock(return_value=(group_ids, ["A", "B"]))

    result = service.create_album("北海道旅行", None, user_id, "owner", group_ids)

    assert result.group_ids == group_ids
    shares = session.add_all.call_args.args[0]
    assert {share.group_id for share in shares} == set(group_ids)
    assert all(isinstance(share, AlbumGroupShare) for share in shares)
    session.commit.assert_called_once_with()


def test_update_album_changes_group_shares_and_prepares_existing_photos() -> None:
    session = MagicMock(spec=Session)
    service, _, photo_sharing = make_service(session)
    album = make_album()
    old_group_id = uuid4()
    new_group_id = uuid4()
    service._get_album_model = MagicMock(return_value=album)
    service._group_ids = MagicMock(return_value=[old_group_id])
    service._album_photo_ids = MagicMock(return_value=[])
    service._prepare_album_photo_sharing = MagicMock(return_value=PreparedAlbumPhotoShares(()))
    service._group_details = MagicMock(return_value=([old_group_id, new_group_id], ["A", "B"]))
    session.scalars.return_value.all.return_value = [new_group_id]

    result = service.update_album(
        album.id,
        title=None,
        description=None,
        update_description=False,
        acting_user_id=uuid4(),
        cover_photo_id=None,
        update_cover=False,
        group_ids=[old_group_id, new_group_id],
        update_groups=True,
        acting_username="owner",
    )

    assert result.group_ids == [old_group_id, new_group_id]
    assert service._get_album_model.call_args.kwargs["requested_group_ids"] == {old_group_id, new_group_id}
    service._prepare_album_photo_sharing.assert_called_once()
    photo_sharing.commit.assert_called_once()
    assert any(isinstance(item, AlbumGroupShare) for item in session.add_all.call_args.args[0])


def test_update_album_rejects_an_added_group_without_membership() -> None:
    session = MagicMock(spec=Session)
    service, _, _ = make_service(session)
    album = make_album()
    old_group_id = uuid4()
    new_group_id = uuid4()
    session.scalars.side_effect = [
        SimpleNamespace(all=lambda: [old_group_id]),
        SimpleNamespace(all=lambda: [old_group_id, new_group_id]),
        SimpleNamespace(all=lambda: [old_group_id]),
        SimpleNamespace(all=lambda: [old_group_id]),
    ]

    with pytest.raises(AlbumNotFoundError):
        service._get_album_model(
            album.id,
            uuid4(),
            lock=True,
            requested_group_ids={old_group_id, new_group_id},
        )

    session.scalar.assert_not_called()
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_update_album_can_clear_description() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    service, _, _ = make_service(session)
    service._get_album_model = MagicMock(return_value=album)
    service._group_details = MagicMock(return_value=([uuid4()], ["A"]))
    session.scalar.side_effect = [4, None]

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
    service, _, _ = make_service(session)
    service._get_album_model = MagicMock(return_value=album)
    service._group_details = MagicMock(return_value=([uuid4()], ["A"]))
    session.scalar.side_effect = [cover_photo_id, 1, cover_photo_id]

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


def test_update_album_rejects_trashed_cover_photo() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    service, _, _ = make_service(session)
    service._get_album_model = MagicMock(return_value=album)
    session.scalar.return_value = None

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


def test_add_photos_prepares_owner_shares_before_registering_membership() -> None:
    session = MagicMock(spec=Session)
    service, catalog, photo_sharing = make_service(session)
    album = make_album()
    photo = make_photo(uploaded_by_user_id=uuid4())
    user_id = photo.uploaded_by_user_id
    group_id = uuid4()
    service._get_album_model = MagicMock(return_value=album)
    service._group_ids = MagicMock(return_value=[group_id])
    service.get_album = MagicMock(return_value=MagicMock(spec=AlbumDetail))
    catalog.list_by_ids.return_value = [photo]
    photo_sharing.prepare_add_groups.return_value = PreparedAlbumPhotoShares(())
    session.scalars.return_value.all.return_value = []

    result = service.add_photos(album.id, [photo.id], user_id, "owner")

    assert result is service.get_album.return_value
    photo_sharing.prepare_add_groups.assert_called_once()
    assert photo_sharing.prepare_add_groups.call_args.args[0] == {photo.id: {group_id}}
    membership = session.add.call_args.args[0]
    assert isinstance(membership, AlbumPhoto)
    assert membership.photo_id == photo.id


def test_add_photos_rejects_missing_photos_before_mutation() -> None:
    session = MagicMock(spec=Session)
    service, catalog, photo_sharing = make_service(session)
    album = make_album()
    existing_id = uuid4()
    missing_id = uuid4()
    service._get_album_model = MagicMock(return_value=album)
    service._group_ids = MagicMock(return_value=[uuid4()])
    catalog.list_by_ids.return_value = [make_photo(photo_id=existing_id)]

    with pytest.raises(PhotoNotFoundError) as error:
        service.add_photos(album.id, [existing_id, missing_id], uuid4())

    assert error.value.photo_ids == {missing_id}
    photo_sharing.prepare_add_groups.assert_not_called()
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_add_photos_only_registers_new_memberships() -> None:
    session = MagicMock(spec=Session)
    service, catalog, photo_sharing = make_service(session)
    album = make_album()
    group_id = uuid4()
    existing_id = uuid4()
    new_id = uuid4()
    photos = [
        make_photo(photo_id=existing_id, visibility=PhotoVisibility.SHARED, group_id=group_id),
        make_photo(photo_id=new_id, visibility=PhotoVisibility.SHARED, group_id=group_id),
    ]
    service._get_album_model = MagicMock(return_value=album)
    service._group_ids = MagicMock(return_value=[group_id])
    service.get_album = MagicMock(return_value=MagicMock(spec=AlbumDetail))
    catalog.list_by_ids.return_value = photos
    photo_sharing.prepare_add_groups.return_value = PreparedAlbumPhotoShares(())
    session.scalars.return_value.all.return_value = [existing_id]

    service.add_photos(album.id, [existing_id, new_id], uuid4())

    membership = session.add.call_args.args[0]
    assert isinstance(membership, AlbumPhoto)
    assert membership.photo_id == new_id
    session.commit.assert_called_once_with()


def test_add_photos_fails_as_a_batch_when_another_users_photo_lacks_a_share() -> None:
    session = MagicMock(spec=Session)
    service, catalog, photo_sharing = make_service(session)
    album = make_album()
    group_id = uuid4()
    owner_id = uuid4()
    viewer_id = uuid4()
    owner_photo = make_photo(uploaded_by_user_id=viewer_id)
    other_photo = make_photo(
        uploaded_by_user_id=owner_id,
        visibility=PhotoVisibility.SHARED,
        group_id=uuid4(),
    )
    service._get_album_model = MagicMock(return_value=album)
    service._group_ids = MagicMock(return_value=[group_id])
    catalog.list_by_ids.return_value = [owner_photo, other_photo]

    with pytest.raises(PhotoNotFoundError) as error:
        service.add_photos(album.id, [owner_photo.id, other_photo.id], viewer_id, "viewer")

    assert error.value.photo_ids == {other_photo.id}
    photo_sharing.prepare_add_groups.assert_not_called()
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_add_photos_rejects_non_owner_photo_missing_a_group() -> None:
    session = MagicMock(spec=Session)
    service, catalog, photo_sharing = make_service(session)
    album = make_album()
    owner_id = uuid4()
    viewer_id = uuid4()
    photo = make_photo(uploaded_by_user_id=owner_id)
    service._get_album_model = MagicMock(return_value=album)
    service._group_ids = MagicMock(return_value=[uuid4()])
    catalog.list_by_ids.return_value = [photo]

    with pytest.raises(PhotoNotFoundError) as error:
        service.add_photos(album.id, [photo.id], viewer_id, "viewer")

    assert error.value.photo_ids == {photo.id}
    photo_sharing.prepare_add_groups.assert_not_called()
    session.add.assert_not_called()


def test_delete_album_deletes_album_for_a_member_of_any_target_group() -> None:
    session = MagicMock(spec=Session)
    service, _, _ = make_service(session)
    album = make_album()
    service._get_album_model = MagicMock(return_value=album)

    service.delete_album(album.id, uuid4())

    session.delete.assert_called_once_with(album)
    session.commit.assert_called_once_with()


def test_remove_photo_raises_when_membership_does_not_exist() -> None:
    session = MagicMock(spec=Session)
    service, _, _ = make_service(session)
    album = make_album()
    service._get_album_model = MagicMock(return_value=album)
    session.execute.return_value.rowcount = 0

    with pytest.raises(PhotoNotInAlbumError):
        service.remove_photo(album.id, uuid4(), uuid4())

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_removed_sharing_also_removes_photo_from_all_albums() -> None:
    session = MagicMock(spec=Session)
    album = make_album()
    photo_id = uuid4()
    album.cover_photo_id = photo_id
    session.scalars.return_value.all.return_value = [album]

    remove_photo_from_all_albums(session, photo_id)

    assert album.cover_photo_id is None
    session.flush.assert_called_once_with()
    statement = session.execute.call_args.args[0]
    assert "DELETE FROM album_photos" in str(statement.compile(dialect=postgresql.dialect()))


def test_persistence_failure_rolls_back() -> None:
    session = MagicMock(spec=Session)
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))
    service, _, _ = make_service(session)
    group_id = uuid4()
    session.scalars.return_value.all.return_value = [group_id]
    service._group_details = MagicMock(return_value=([group_id], ["A"]))

    def fail_commit(_prepared: PreparedAlbumPhotoShares) -> None:
        session.rollback()
        raise AlbumPhotoSharingError

    service._photo_sharing.commit.side_effect = fail_commit

    with pytest.raises(AlbumPersistenceError):
        service.create_album("北海道旅行", None, uuid4(), "owner", [group_id])

    session.rollback.assert_called_once_with()
