from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.features.notifications.public import NotificationType
from app.features.photos import album_sharing as album_sharing_module
from app.features.photos.album_sharing import AlbumPhotoSharingPermissionError, PhotoAlbumSharingService
from app.features.photos.models import PhotoActivityEventType
from app.features.photos.storage.facade import PhotoStorage
from tests.features.photos.factories import make_photo


def result_with(items):
    result = MagicMock()
    result.all.return_value = items
    return result


def test_prepare_add_groups_updates_sidecar_activity_and_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    storage = MagicMock(spec=PhotoStorage)
    owner_id = uuid4()
    group_id = uuid4()
    photo = make_photo(uploaded_by_user_id=owner_id)
    session.scalars.side_effect = [result_with([group_id]), result_with([group_id]), result_with([photo])]
    notify = MagicMock()
    monkeypatch.setattr(album_sharing_module, "enqueue_group_notification", notify)
    service = PhotoAlbumSharingService(session, storage)

    prepared = service.prepare_add_groups({photo.id: {group_id}}, owner_id, "owner")

    assert {share.group_id for share in photo.shares} == {group_id}
    assert photo.metadata_version == 2
    assert prepared.previous_metadata[0].group_ids == ()
    assert storage.update_sidecar.call_args.args[0].group_ids == (group_id,)
    event = session.add.call_args.args[0]
    assert event.event_type is PhotoActivityEventType.SHARED
    assert [item.group_id for item in event.groups] == [group_id]
    notify.assert_called_once()
    assert notify.call_args.args[:3] == (session, {group_id}, NotificationType.PHOTO_SHARED)
    assert notify.call_args.kwargs["exclude_user_id"] == owner_id
    session.commit.assert_not_called()

    service.commit(prepared)

    session.commit.assert_called_once_with()


def test_prepare_add_groups_rejects_groups_without_membership() -> None:
    session = MagicMock(spec=Session)
    storage = MagicMock(spec=PhotoStorage)
    session.scalars.return_value = result_with([])
    service = PhotoAlbumSharingService(session, storage)

    with pytest.raises(AlbumPhotoSharingPermissionError):
        service.prepare_add_groups({uuid4(): {uuid4()}}, uuid4(), "owner")

    storage.update_sidecar.assert_not_called()
    session.commit.assert_not_called()
