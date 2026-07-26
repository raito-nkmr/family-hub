from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.features.shopping.models import ShoppingItem


def make_shopping_item(
    *,
    item_id: UUID | None = None,
    group_id: UUID | None = None,
    created_by_user_id: UUID | None = None,
    name: str = "牛乳",
    purchased_by_user_id: UUID | None = None,
) -> ShoppingItem:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return ShoppingItem(
        id=item_id or uuid4(),
        group_id=group_id or uuid4(),
        name=name,
        created_by_user_id=created_by_user_id or uuid4(),
        purchased_by_user_id=purchased_by_user_id,
        created_at=now,
        updated_at=now,
        purchased_at=datetime(2026, 7, 15, 8, tzinfo=UTC) if purchased_by_user_id else None,
    )
