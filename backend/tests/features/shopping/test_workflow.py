from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.features.auth.public import PublicUser, UserDirectory
from app.features.groups.models import FamilyGroupMember
from app.features.shopping.models import ShoppingItem, ShoppingPurchase, ShoppingTrip
from app.features.shopping.workflow import (
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
    session.scalars.return_value.all.return_value = [group_id]
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
