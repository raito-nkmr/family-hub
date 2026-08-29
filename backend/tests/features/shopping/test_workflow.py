from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.features.auth.public import PublicUser, UserDirectory
from app.features.groups.models import FamilyGroupMember
from app.features.shopping.models import ShoppingItem, ShoppingPurchase, ShoppingTrip
from app.features.shopping.workflow import (
    UNSET,
    ShoppingWorkflowConflictError,
    ShoppingWorkflowNotFoundError,
    ShoppingWorkflowService,
)
from tests.features.shopping.factories import make_shopping_item


def make_service(session: Session) -> tuple[ShoppingWorkflowService, MagicMock]:
    directory = MagicMock(spec=UserDirectory)
    return ShoppingWorkflowService(session, directory), directory


def make_member(group_id, user_id) -> FamilyGroupMember:
    return FamilyGroupMember(group_id=group_id, user_id=user_id, role="member")


def test_create_item_accepts_another_group_member_as_assignee() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    creator_id = uuid4()
    assignee_id = uuid4()
    creator_membership = make_member(group_id, creator_id)
    assignee_membership = make_member(group_id, assignee_id)
    session.scalars.return_value.all.side_effect = [[group_id], [group_id], []]
    session.get.side_effect = [creator_membership, assignee_membership]
    directory = MagicMock(spec=UserDirectory)
    directory.list_by_ids.return_value = {
        creator_id: PublicUser(id=creator_id, username="creator", is_active=True),
        assignee_id: PublicUser(id=assignee_id, username="assignee", is_active=True),
    }
    service = ShoppingWorkflowService(session, directory)

    result = service.create_item(group_id, creator_id, "牛乳", assignee_id, None)

    created = session.add.call_args.args[0]
    assert isinstance(created, ShoppingItem)
    assert created.assignee_user_id == assignee_id
    assert result.assignee_username == "assignee"


def test_create_item_rejects_an_assignee_outside_the_group() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    creator_id = uuid4()
    session.scalars.return_value.all.return_value = [group_id]
    session.get.side_effect = [make_member(group_id, creator_id), None]
    service, _ = make_service(session)

    with pytest.raises(ShoppingWorkflowNotFoundError):
        service.create_item(group_id, creator_id, "牛乳", uuid4(), None)

    session.commit.assert_not_called()


def test_purchase_records_actual_buyer_separately_from_assignee() -> None:
    session = MagicMock(spec=Session)
    item = make_shopping_item()
    item.assignee_user_id = uuid4()
    buyer_id = uuid4()
    session.scalar.side_effect = [item.group_id, item, None]
    session.scalars.return_value.all.return_value = [item.group_id]
    session.get.return_value = make_member(item.group_id, buyer_id)
    service, directory = make_service(session)
    directory.list_by_ids.side_effect = [
        {item.assignee_user_id: PublicUser(id=item.assignee_user_id, username="依頼先", is_active=True)},
        {buyer_id: PublicUser(id=buyer_id, username="購入者", is_active=True)},
    ]

    result = service.purchase_item(item.id, buyer_id)

    purchase = session.add.call_args.args[0]
    assert isinstance(purchase, ShoppingPurchase)
    assert purchase.assignee_user_id == item.assignee_user_id
    assert purchase.purchased_by_user_id == buyer_id
    assert result.assignee_username == "依頼先"
    assert result.purchased_by_username == "購入者"


def test_unplanned_purchase_has_no_list_item_reference() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    buyer_id = uuid4()
    trip = ShoppingTrip(
        id=uuid4(),
        group_id=group_id,
        started_by_user_id=buyer_id,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.scalar.side_effect = [group_id, trip]
    session.scalars.return_value.all.return_value = [group_id]
    session.get.return_value = make_member(group_id, buyer_id)
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        buyer_id: PublicUser(id=buyer_id, username="購入者", is_active=True),
    }

    result = service.add_unplanned_purchase(trip.id, buyer_id, "電池", None, None)

    purchase = session.add.call_args.args[0]
    assert isinstance(purchase, ShoppingPurchase)
    assert purchase.shopping_item_id is None
    assert result.item_name == "電池"


def test_workflow_purchase_row_is_saved_with_current_buyer() -> None:
    session = MagicMock(spec=Session)
    item = make_shopping_item()
    buyer_id = uuid4()
    session.scalar.side_effect = [item.group_id, item, None]
    session.scalars.return_value.all.return_value = [item.group_id]
    session.get.return_value = make_member(item.group_id, buyer_id)
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        buyer_id: PublicUser(id=buyer_id, username="購入者", is_active=True),
    }

    service.purchase_item(item.id, buyer_id)

    assert item.purchased_by_user_id == buyer_id
    assert item.purchased_at is not None
    session.flush.assert_called_once()


def test_start_trip_reuses_latest_in_progress_trip() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    trip = ShoppingTrip(
        id=uuid4(),
        group_id=group_id,
        started_by_user_id=user_id,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.scalar.return_value = trip
    session.scalars.return_value.all.side_effect = [[group_id], [group_id], []]
    session.get.return_value = make_member(group_id, user_id)
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        user_id: PublicUser(id=user_id, username="購入者", is_active=True),
    }

    result = service.start_trip(group_id, user_id)

    assert result.id == trip.id
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_list_trips_hides_discarded_trips_by_default() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    session.get.return_value = make_member(group_id, user_id)
    session.scalars.return_value.all.return_value = []
    service, _ = make_service(session)

    service.list_trips(group_id, user_id, None)
    default_statement = str(session.scalars.call_args.args[0])

    service.list_trips(group_id, user_id, None, include_discarded=True)
    audit_statement = str(session.scalars.call_args.args[0])

    assert "shopping_trips.discarded_at IS NULL" in default_statement
    assert "shopping_trips.discarded_at IS NULL" not in audit_statement


def test_discard_trip_reverses_purchases_and_restores_items() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    item = make_shopping_item(group_id=group_id, purchased_by_user_id=user_id)
    trip = ShoppingTrip(
        id=uuid4(),
        group_id=group_id,
        started_by_user_id=user_id,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    purchase = ShoppingPurchase(
        id=uuid4(),
        group_id=group_id,
        trip_id=trip.id,
        shopping_item_id=item.id,
        item_name_snapshot=item.name,
        purchased_by_user_id=user_id,
        purchased_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.scalar.side_effect = [group_id, trip, item, None]
    session.scalars.return_value.all.side_effect = [[group_id], [group_id], [purchase]]
    session.get.return_value = make_member(group_id, user_id)
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        user_id: PublicUser(id=user_id, username="購入者", is_active=True),
    }

    result = service.discard_trip(trip.id, user_id)

    assert result.id == trip.id
    assert trip.discarded_at is not None
    assert trip.discarded_by_user_id == user_id
    assert purchase.reversed_at is not None
    assert purchase.reversed_by_user_id == user_id
    assert item.purchased_at is None
    assert item.purchased_by_user_id is None
    session.commit.assert_called_once()


def test_discarded_trip_rejects_amount_changes() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    trip = ShoppingTrip(
        id=uuid4(),
        group_id=group_id,
        started_by_user_id=user_id,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        discarded_at=datetime.now(UTC),
        discarded_by_user_id=user_id,
    )
    session.scalar.side_effect = [group_id, trip]
    session.scalars.return_value.all.return_value = [group_id]
    session.get.return_value = make_member(group_id, user_id)
    service, _ = make_service(session)

    with pytest.raises(ShoppingWorkflowConflictError):
        service.update_trip(trip.id, user_id, 1000, True)

    session.commit.assert_not_called()


def test_delete_empty_in_progress_trip_is_allowed() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    trip = ShoppingTrip(
        id=uuid4(),
        group_id=group_id,
        started_by_user_id=user_id,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.scalar.side_effect = [group_id, trip]
    session.scalars.return_value.all.side_effect = [[group_id], [group_id], []]
    session.get.return_value = make_member(group_id, user_id)
    service, _ = make_service(session)

    service.delete_trip(trip.id, user_id)

    session.delete.assert_called_once_with(trip)
    session.commit.assert_called_once()


def test_delete_finalized_trip_removes_purchases_and_restores_list_items() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    item = make_shopping_item(group_id=group_id, created_by_user_id=user_id, purchased_by_user_id=user_id)
    trip = ShoppingTrip(
        id=uuid4(),
        group_id=group_id,
        started_by_user_id=user_id,
        started_at=datetime.now(UTC),
        finalized_at=datetime.now(UTC),
        total_amount_yen=1800,
        recorded_by_user_id=user_id,
        updated_at=datetime.now(UTC),
    )
    purchase = ShoppingPurchase(
        id=uuid4(),
        group_id=group_id,
        trip_id=trip.id,
        shopping_item_id=item.id,
        item_name_snapshot=item.name,
        purchased_by_user_id=user_id,
        purchased_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.scalar.side_effect = [group_id, trip, item, None]
    session.scalars.return_value.all.side_effect = [[group_id], [group_id], [purchase]]
    session.get.return_value = make_member(group_id, user_id)
    service, _ = make_service(session)

    service.delete_trip(trip.id, user_id)

    assert item.purchased_at is None
    assert item.purchased_by_user_id is None
    assert session.delete.call_args_list == [((purchase,), {}), ((trip,), {})]
    session.commit.assert_called_once()


def test_finishing_empty_trip_deletes_it_atomically() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    trip = ShoppingTrip(
        id=uuid4(),
        group_id=group_id,
        started_by_user_id=user_id,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.scalar.side_effect = [group_id, trip]
    session.scalars.return_value.all.side_effect = [[group_id], [group_id], []]
    session.get.return_value = make_member(group_id, user_id)
    service, _ = make_service(session)

    result = service.update_trip(trip.id, user_id, None, True, True)

    assert result is None
    session.delete.assert_called_once_with(trip)
    session.commit.assert_called_once()


def test_updating_trip_without_amount_preserves_existing_amount() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    trip = ShoppingTrip(
        id=uuid4(),
        group_id=group_id,
        started_by_user_id=user_id,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        total_amount_yen=1250,
    )
    session.scalar.side_effect = [group_id, trip]
    session.scalars.return_value.all.side_effect = [[group_id], [group_id], []]
    session.get.return_value = make_member(group_id, user_id)
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        user_id: PublicUser(id=user_id, username="購入者", is_active=True),
    }

    service.update_trip(trip.id, user_id, UNSET, True)

    assert trip.total_amount_yen == 1250
    assert trip.finalized_at is not None
    session.commit.assert_called_once()


def test_updating_purchase_without_fields_preserves_existing_values() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    category_id = uuid4()
    purchase = ShoppingPurchase(
        id=uuid4(),
        group_id=group_id,
        trip_id=uuid4(),
        item_name_snapshot="電池",
        category_id=category_id,
        category_name_snapshot="日用品",
        purchased_by_user_id=user_id,
        purchased_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    trip = ShoppingTrip(
        id=purchase.trip_id,
        group_id=group_id,
        started_by_user_id=user_id,
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.scalar.side_effect = [group_id, purchase, trip]
    session.scalars.return_value.all.return_value = [group_id]
    session.get.return_value = make_member(group_id, user_id)
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        user_id: PublicUser(id=user_id, username="購入者", is_active=True),
    }

    service.update_purchase(purchase.id, user_id, UNSET, UNSET)

    assert purchase.category_id == category_id
    assert purchase.category_name_snapshot == "日用品"
    assert purchase.purchased_by_user_id == user_id
    session.commit.assert_called_once()
