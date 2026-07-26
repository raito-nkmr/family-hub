from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.features.auth.public import PublicUser, UserDirectory
from app.features.groups.models import GroupRole
from app.features.shopping.models import ShoppingItem
from app.features.shopping.service import ShoppingNotFoundError, ShoppingService, ShoppingStateConflictError
from tests.features.groups.factories import make_membership
from tests.features.shopping.factories import make_shopping_item


def make_service(session: Session) -> tuple[ShoppingService, MagicMock]:
    directory = MagicMock(spec=UserDirectory)
    return ShoppingService(session, directory), directory


def test_list_items_returns_active_then_recent_purchased_with_actor() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    group_id = uuid4()
    purchased = make_shopping_item(group_id=group_id, purchased_by_user_id=user_id)
    active = make_shopping_item(group_id=group_id)
    session.get.return_value = make_membership(group_id, user_id)
    session.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[active])),
        MagicMock(all=MagicMock(return_value=[purchased])),
    ]
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {user_id: PublicUser(id=user_id, username="buyer", is_active=True)}

    result = service.list_items(group_id, user_id)

    assert [item.id for item in result] == [active.id, purchased.id]
    assert result[1].purchased_by_username == "buyer"


def test_create_item_is_available_to_group_member() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    session.get.return_value = make_membership(group_id, user_id, role=GroupRole.MEMBER)
    session.scalars.return_value.all.return_value = [group_id]
    service, _ = make_service(session)

    result = service.create_item(group_id, user_id, "牛乳")

    item = session.add.call_args.args[0]
    assert isinstance(item, ShoppingItem)
    assert result.name == "牛乳"
    assert result.purchased_at is None
    session.commit.assert_called_once_with()


def test_purchase_item_records_actor_and_time() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    item = make_shopping_item()
    session.scalar.side_effect = [item.group_id, item]
    session.get.return_value = make_membership(item.group_id, user_id)
    session.scalars.return_value.all.return_value = [item.group_id]
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {user_id: PublicUser(id=user_id, username="buyer", is_active=True)}

    result = service.purchase_item(item.id, user_id)

    assert item.purchased_by_user_id == user_id
    assert item.purchased_at is not None
    assert result.purchased_by_username == "buyer"
    session.commit.assert_called_once_with()


def test_restore_item_clears_purchase_state() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    item = make_shopping_item(purchased_by_user_id=user_id)
    session.scalar.side_effect = [item.group_id, item]
    session.get.return_value = make_membership(item.group_id, user_id)
    session.scalars.return_value.all.return_value = [item.group_id]
    service, _ = make_service(session)

    result = service.restore_item(item.id, user_id)

    assert result.purchased_at is None
    assert result.purchased_by_user_id is None


def test_purchase_rejects_already_purchased_item() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    item = make_shopping_item(purchased_by_user_id=user_id)
    session.scalar.side_effect = [item.group_id, item]
    session.get.return_value = make_membership(item.group_id, user_id)
    session.scalars.return_value.all.return_value = [item.group_id]
    service, _ = make_service(session)

    with pytest.raises(ShoppingStateConflictError):
        service.purchase_item(item.id, user_id)


def test_non_member_cannot_discover_item() -> None:
    session = MagicMock(spec=Session)
    item = make_shopping_item()
    session.scalar.return_value = item.group_id
    session.scalars.return_value.all.return_value = []
    service, _ = make_service(session)

    with pytest.raises(ShoppingNotFoundError):
        service.purchase_item(item.id, uuid4())

    session.get.assert_not_called()
