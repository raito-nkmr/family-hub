from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.commands.delete_group import (
    GroupDeletionChangedError,
    GroupDeletionConfirmationError,
    GroupDeletionHasRelatedDataError,
    GroupDeletionImpact,
    GroupDeletionPersistenceError,
    confirm_group_deletion,
    delete_group,
    get_group_deletion_impact,
    print_deletion_impact,
    sync_affected_photo_sidecars,
)
from tests.features.photos.factories import make_photo


def make_impact(**overrides: object) -> GroupDeletionImpact:
    values: dict[str, object] = {
        "group_id": uuid4(),
        "name": "同居家族",
        "member_count": 2,
        "album_count": 0,
        "album_photo_count": 0,
        "chore_task_count": 0,
        "chore_completion_count": 0,
        "shopping_item_count": 0,
        "shopping_category_count": 0,
        "shopping_trip_count": 0,
        "shopping_purchase_count": 0,
        "photo_share_count": 0,
        "photo_activity_group_count": 0,
        "upload_batch_group_share_count": 0,
        "membership_invitation_count": 0,
    }
    values.update(overrides)
    return GroupDeletionImpact(**values)  # type: ignore[arg-type]


def test_get_group_deletion_impact_returns_all_cascade_counts() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    session.execute.return_value.one_or_none.return_value = ("同居家族", 2, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)

    impact = get_group_deletion_impact(session, group_id, lock=True)

    assert impact == GroupDeletionImpact(group_id, "同居家族", 2, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
    sql = str(
        session.execute.call_args.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "FOR UPDATE OF family_groups" in sql
    assert "photo_activity_event_groups" in sql
    assert "upload_batch_group_shares" in sql


def test_memberships_alone_do_not_require_related_data_option() -> None:
    assert make_impact().has_related_data is False
    assert make_impact(album_count=1).has_related_data is True


@pytest.mark.parametrize(
    "field_name",
    ["shopping_category_count", "shopping_trip_count", "shopping_purchase_count"],
)
def test_shopping_history_alone_requires_related_data_option(field_name: str) -> None:
    assert make_impact(**{field_name: 1}).has_related_data is True


def test_confirmation_requires_exact_group_name() -> None:
    impact = make_impact()

    confirm_group_deletion(impact, read_confirmation=lambda _: "同居家族")

    with pytest.raises(GroupDeletionConfirmationError):
        confirm_group_deletion(impact, read_confirmation=lambda _: "同居家族 ")


@pytest.mark.parametrize(
    "field_name",
    ["shopping_category_count", "shopping_item_count", "shopping_trip_count", "shopping_purchase_count"],
)
def test_delete_group_rejects_shopping_data_without_explicit_option(
    field_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock(spec=Session)
    impact = make_impact(**{field_name: 1})
    monkeypatch.setattr("app.commands.delete_group.get_group_deletion_impact", MagicMock(return_value=impact))

    with pytest.raises(GroupDeletionHasRelatedDataError):
        delete_group(session, impact, include_related_data=False)

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_delete_group_aborts_if_data_changed_after_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    impact = make_impact()
    changed = make_impact(group_id=impact.group_id, shopping_item_count=1)
    monkeypatch.setattr("app.commands.delete_group.get_group_deletion_impact", MagicMock(return_value=changed))

    with pytest.raises(GroupDeletionChangedError):
        delete_group(session, impact, include_related_data=True)

    session.rollback.assert_called_once_with()


def test_delete_group_collects_affected_photos_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    impact = make_impact(photo_share_count=2)
    photo_ids = [uuid4(), uuid4()]
    session.scalars.return_value.all.return_value = photo_ids
    monkeypatch.setattr("app.commands.delete_group.get_group_deletion_impact", MagicMock(return_value=impact))

    result = delete_group(session, impact, include_related_data=True)

    assert result == tuple(photo_ids)
    delete_statement = session.execute.call_args.args[0]
    assert "DELETE FROM family_groups" in str(delete_statement.compile(dialect=postgresql.dialect()))
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_delete_group_rolls_back_database_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    impact = make_impact()
    session.execute.side_effect = OperationalError("delete", {}, RuntimeError("database unavailable"))
    monkeypatch.setattr("app.commands.delete_group.get_group_deletion_impact", MagicMock(return_value=impact))

    with pytest.raises(GroupDeletionPersistenceError):
        delete_group(session, impact, include_related_data=False)

    session.rollback.assert_called_once_with()


def test_sync_affected_photo_sidecars_rewrites_only_existing_photos() -> None:
    session = MagicMock(spec=Session)
    photos = [make_photo(), make_photo()]
    session.scalars.return_value.all.return_value = photos
    storage = MagicMock()

    synced_count = sync_affected_photo_sidecars(
        session,
        storage,
        tuple(photo.id for photo in photos) + (uuid4(),),
    )

    assert synced_count == 2
    assert [call.args[0].photo_id for call in storage.update_sidecar.call_args_list] == [photo.id for photo in photos]


def test_sync_affected_photo_sidecars_skips_query_when_no_photos_are_shared() -> None:
    session = MagicMock(spec=Session)
    storage = MagicMock()

    assert sync_affected_photo_sidecars(session, storage, ()) == 0
    session.scalars.assert_not_called()
    storage.update_sidecar.assert_not_called()


def test_print_deletion_impact_warns_that_photos_remain(capsys: pytest.CaptureFixture[str]) -> None:
    print_deletion_impact(
        make_impact(
            photo_share_count=2,
            shopping_category_count=1,
            shopping_trip_count=2,
            shopping_purchase_count=3,
        )
    )

    output = capsys.readouterr().out
    assert "Photo shares: 2" in output
    assert "Shopping categories: 1" in output
    assert "Shopping trips: 2" in output
    assert "Shopping purchases: 3" in output
    assert "original photo files will not be deleted" in output
