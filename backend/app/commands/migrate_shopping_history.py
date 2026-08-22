"""Convert legacy shopping purchase state into durable purchase events."""

import argparse
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.shopping.models import ShoppingCategory, ShoppingItem, ShoppingPurchase, ShoppingTrip


def migrate(session: Session, *, apply: bool) -> int:
    legacy_items = list(
        session.scalars(
            select(ShoppingItem).where(
                ShoppingItem.purchased_at.is_not(None),
                ShoppingItem.purchased_by_user_id.is_not(None),
            )
        ).all()
    )
    migrated = 0
    for item in legacy_items:
        if session.scalar(select(ShoppingPurchase.id).where(ShoppingPurchase.shopping_item_id == item.id)) is not None:
            continue
        category_name = None
        if item.category_id is not None:
            category_name = session.scalar(select(ShoppingCategory.name).where(ShoppingCategory.id == item.category_id))
        trip = ShoppingTrip(
            id=uuid4(),
            group_id=item.group_id,
            started_by_user_id=item.purchased_by_user_id,
            started_at=item.purchased_at,
            finalized_at=item.purchased_at,
            recorded_by_user_id=item.purchased_by_user_id,
            updated_at=item.updated_at,
        )
        purchase = ShoppingPurchase(
            id=uuid4(),
            group_id=item.group_id,
            trip_id=trip.id,
            shopping_item_id=item.id,
            item_name_snapshot=item.name,
            assignee_user_id=item.assignee_user_id,
            category_id=item.category_id,
            category_name_snapshot=category_name,
            purchased_by_user_id=item.purchased_by_user_id,
            purchased_at=item.purchased_at,
            updated_at=item.updated_at,
        )
        session.add_all([trip, purchase])
        migrated += 1
    if apply:
        session.commit()
    else:
        session.rollback()
    return migrated


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy shopping purchase state into history events")
    parser.add_argument("--apply", action="store_true", help="Commit the migration")
    arguments = parser.parse_args()
    settings = get_management_settings()
    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as session:
            migrated = migrate(session, apply=arguments.apply)
    finally:
        engine.dispose()
    action = "Migrated" if arguments.apply else "Would migrate"
    print(f"{action} {migrated} shopping purchase(s)")


if __name__ == "__main__":
    main()
