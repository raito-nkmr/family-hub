from unittest.mock import Mock

from app.commands.sync_photo_sidecars import sync_photo_sidecars
from tests.features.photos.factories import make_photo


def test_sync_photo_sidecars_rewrites_each_photo_from_database_state() -> None:
    photos = [make_photo(), make_photo()]
    session = Mock()
    session.scalars.return_value.all.return_value = photos
    storage = Mock()

    synced_count = sync_photo_sidecars(session, storage)

    assert synced_count == 2
    assert storage.update_sidecar.call_count == 2
    assert [call.args[0].photo_id for call in storage.update_sidecar.call_args_list] == [photo.id for photo in photos]
