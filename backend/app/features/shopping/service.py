from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.auth.public import UserDirectory
from app.features.groups.public import FamilyGroupMember, lock_user_group_ids
from app.features.notifications.public import NotificationType, enqueue_group_notification
from app.features.shopping.models import ShoppingItem

RECENT_PURCHASED_LIMIT = 20


class ShoppingNotFoundError(Exception):
    pass


class ShoppingStateConflictError(Exception):
    pass


class ShoppingPersistenceError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ShoppingItemSummary:
    id: UUID
    group_id: UUID
    name: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    purchased_by_user_id: UUID | None
    purchased_by_username: str | None
    purchased_at: datetime | None


class ShoppingService:
    def __init__(self, session: Session, user_directory: UserDirectory) -> None:
        self._session = session
        self._user_directory = user_directory

    def list_items(self, group_id: UUID, user_id: UUID) -> list[ShoppingItemSummary]:
        self._require_membership(group_id, user_id)
        active = list(
            self._session.scalars(
                select(ShoppingItem)
                .where(ShoppingItem.group_id == group_id, ShoppingItem.purchased_at.is_(None))
                .order_by(ShoppingItem.created_at.asc(), ShoppingItem.id.asc())
            ).all()
        )
        purchased = list(
            self._session.scalars(
                select(ShoppingItem)
                .where(ShoppingItem.group_id == group_id, ShoppingItem.purchased_at.is_not(None))
                .order_by(ShoppingItem.purchased_at.desc(), ShoppingItem.id.desc())
                .limit(RECENT_PURCHASED_LIMIT)
            ).all()
        )
        return self._summaries([*active, *purchased])

    def create_item(self, group_id: UUID, user_id: UUID, name: str) -> ShoppingItemSummary:
        self._lock_membership(group_id, user_id)
        now = datetime.now(UTC)
        item = ShoppingItem(
            id=uuid4(),
            group_id=group_id,
            name=name,
            created_by_user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(item)
        enqueue_group_notification(
            self._session,
            {group_id},
            NotificationType.SHOPPING_ADDED,
            f"shopping:{item.id}",
            {"url": "/shopping", "item_id": str(item.id)},
            exclude_user_id=user_id,
        )
        self._commit("Could not create shopping item")
        return self._summary(item, None)

    def purchase_item(self, item_id: UUID, user_id: UUID) -> ShoppingItemSummary:
        group_id = self._item_group_id(item_id)
        self._lock_membership(group_id, user_id)
        item = self._locked_item(item_id)
        if item.group_id != group_id:
            raise ShoppingNotFoundError
        if item.purchased_at is not None:
            raise ShoppingStateConflictError
        now = datetime.now(UTC)
        item.purchased_by_user_id = user_id
        item.purchased_at = now
        item.updated_at = now
        self._commit("Could not purchase shopping item")
        username = self._user_directory.list_by_ids({user_id})[user_id].username
        return self._summary(item, username)

    def restore_item(self, item_id: UUID, user_id: UUID) -> ShoppingItemSummary:
        group_id = self._item_group_id(item_id)
        self._lock_membership(group_id, user_id)
        item = self._locked_item(item_id)
        if item.group_id != group_id:
            raise ShoppingNotFoundError
        if item.purchased_at is None:
            raise ShoppingStateConflictError
        item.purchased_by_user_id = None
        item.purchased_at = None
        item.updated_at = datetime.now(UTC)
        self._commit("Could not restore shopping item")
        return self._summary(item, None)

    def _locked_item(self, item_id: UUID) -> ShoppingItem:
        item = self._session.scalar(select(ShoppingItem).where(ShoppingItem.id == item_id).with_for_update())
        if item is None:
            raise ShoppingNotFoundError
        return item

    def _item_group_id(self, item_id: UUID) -> UUID:
        group_id = self._session.scalar(select(ShoppingItem.group_id).where(ShoppingItem.id == item_id))
        if group_id is None:
            raise ShoppingNotFoundError
        return group_id

    def _require_membership(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        membership = self._session.get(FamilyGroupMember, (group_id, user_id))
        if membership is None:
            raise ShoppingNotFoundError
        return membership

    def _lock_membership(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        if group_id not in lock_user_group_ids(self._session, user_id, {group_id}):
            raise ShoppingNotFoundError
        return self._require_membership(group_id, user_id)

    def _summaries(self, items: list[ShoppingItem]) -> list[ShoppingItemSummary]:
        purchased_user_ids = {item.purchased_by_user_id for item in items if item.purchased_by_user_id is not None}
        users = self._user_directory.list_by_ids(purchased_user_ids) if purchased_user_ids else {}
        return [
            self._summary(
                item,
                users[item.purchased_by_user_id].username
                if item.purchased_by_user_id is not None and item.purchased_by_user_id in users
                else None,
            )
            for item in items
        ]

    @staticmethod
    def _summary(item: ShoppingItem, purchased_by_username: str | None) -> ShoppingItemSummary:
        return ShoppingItemSummary(
            id=item.id,
            group_id=item.group_id,
            name=item.name,
            created_by_user_id=item.created_by_user_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            purchased_by_user_id=item.purchased_by_user_id,
            purchased_by_username=purchased_by_username,
            purchased_at=item.purchased_at,
        )

    def _commit(self, message: str) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise ShoppingPersistenceError(message) from error
