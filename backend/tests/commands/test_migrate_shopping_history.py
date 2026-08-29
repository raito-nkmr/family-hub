from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from app.commands.migrate_shopping_history import migrate
from app.features.shopping.models import ShoppingItem, ShoppingPurchase, ShoppingTrip


def test_migrate_shopping_history_is_idempotent_and_dry_run_rolls_back() -> None:
    session = MagicMock()
    item = ShoppingItem(
        id=uuid4(),
        group_id=uuid4(),
        name="牛乳",
        created_by_user_id=uuid4(),
        purchased_by_user_id=uuid4(),
        purchased_at=datetime(2026, 7, 15, tzinfo=UTC),
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
        updated_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    session.scalars.return_value.all.return_value = [item]
    session.scalar.side_effect = [None]

    assert migrate(session, apply=False) == 1
    trip, purchase = session.add_all.call_args.args[0]
    assert isinstance(trip, ShoppingTrip)
    assert isinstance(purchase, ShoppingPurchase)
    assert purchase.trip_id == trip.id
    assert purchase.purchased_at == item.purchased_at
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()

    session.scalar.side_effect = [purchase.id]
    assert migrate(session, apply=True) == 0
    session.commit.assert_called_once_with()
