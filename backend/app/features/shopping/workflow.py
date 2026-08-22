import base64
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.auth.public import UserDirectory
from app.features.groups.public import FamilyGroup, FamilyGroupMember, lock_user_group_ids
from app.features.shopping.models import ShoppingCategory, ShoppingItem, ShoppingPurchase, ShoppingTrip


class ShoppingWorkflowNotFoundError(Exception):
    pass


class ShoppingWorkflowConflictError(Exception):
    pass


class ShoppingWorkflowForbiddenError(Exception):
    pass


class ShoppingWorkflowPersistenceError(Exception):
    pass


class ShoppingCategoryDuplicateError(Exception):
    pass


class ShoppingCategoryInUseError(Exception):
    pass


class ShoppingInvalidCursorError(Exception):
    pass


class ShoppingInvalidDateRangeError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ShoppingCategorySummary:
    id: UUID
    group_id: UUID
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ShoppingListItemSummary:
    id: UUID
    group_id: UUID
    name: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    assignee_user_id: UUID | None
    assignee_username: str | None
    category_id: UUID | None
    category_name: str | None


@dataclass(frozen=True, slots=True)
class ShoppingPurchaseSummary:
    id: UUID
    trip_id: UUID
    shopping_item_id: UUID | None
    item_name: str
    assignee_user_id: UUID | None
    assignee_username: str | None
    category_id: UUID | None
    category_name: str | None
    purchased_by_user_id: UUID
    purchased_by_username: str
    purchased_at: datetime
    reversed_at: datetime | None
    reversed_by_user_id: UUID | None


@dataclass(frozen=True, slots=True)
class ShoppingTripSummary:
    id: UUID
    group_id: UUID
    started_by_user_id: UUID
    started_by_username: str
    started_at: datetime
    finalized_at: datetime | None
    total_amount_yen: int | None
    recorded_by_user_id: UUID | None
    recorded_by_username: str | None
    updated_at: datetime
    purchase_count: int
    active_purchase_count: int
    purchases: list[ShoppingPurchaseSummary]


class ShoppingWorkflowService:
    def __init__(self, session: Session, user_directory: UserDirectory) -> None:
        self._session = session
        self._user_directory = user_directory

    def list_items(self, group_id: UUID, user_id: UUID) -> list[ShoppingListItemSummary]:
        self._require_membership(group_id, user_id)
        items = list(
            self._session.scalars(
                select(ShoppingItem)
                .where(ShoppingItem.group_id == group_id, ShoppingItem.purchased_at.is_(None))
                .order_by(ShoppingItem.created_at.asc(), ShoppingItem.id.asc())
            ).all()
        )
        return self._item_summaries(items)

    def create_item(
        self,
        group_id: UUID,
        user_id: UUID,
        name: str,
        assignee_user_id: UUID | None,
        category_id: UUID | None,
    ) -> ShoppingListItemSummary:
        self._lock_membership(group_id, user_id)
        self._validate_assignment(group_id, assignee_user_id)
        self._validate_category(group_id, category_id)
        now = datetime.now(UTC)
        item = ShoppingItem(
            id=uuid4(),
            group_id=group_id,
            name=name.strip(),
            created_by_user_id=user_id,
            created_at=now,
            updated_at=now,
            assignee_user_id=assignee_user_id,
            category_id=category_id,
        )
        self._session.add(item)
        self._commit("Could not create shopping item")
        return self._item_summaries([item])[0]

    def update_item(
        self,
        item_id: UUID,
        user_id: UUID,
        name: str,
        assignee_user_id: UUID | None,
        category_id: UUID | None,
    ) -> ShoppingListItemSummary:
        group_id = self._item_group_id(item_id)
        self._lock_membership(group_id, user_id)
        self._validate_assignment(group_id, assignee_user_id)
        self._validate_category(group_id, category_id)
        item = self._locked_item(item_id)
        if item.group_id != group_id:
            raise ShoppingWorkflowNotFoundError
        if item.purchased_at is not None:
            raise ShoppingWorkflowConflictError
        item.name = name.strip()
        item.assignee_user_id = assignee_user_id
        item.category_id = category_id
        item.updated_at = datetime.now(UTC)
        self._commit("Could not update shopping item")
        return self._item_summaries([item])[0]

    def delete_item(self, item_id: UUID, user_id: UUID) -> None:
        group_id = self._item_group_id(item_id)
        self._lock_membership(group_id, user_id)
        item = self._locked_item(item_id)
        if item.group_id != group_id:
            raise ShoppingWorkflowNotFoundError
        if item.purchased_at is not None:
            raise ShoppingWorkflowConflictError
        self._session.delete(item)
        self._commit("Could not delete shopping item")

    def list_categories(self, group_id: UUID, user_id: UUID) -> list[ShoppingCategorySummary]:
        self._require_membership(group_id, user_id)
        categories = list(
            self._session.scalars(
                select(ShoppingCategory)
                .where(ShoppingCategory.group_id == group_id)
                .order_by(ShoppingCategory.sort_order.asc(), ShoppingCategory.name.asc(), ShoppingCategory.id.asc())
            ).all()
        )
        return [self._category_summary(category) for category in categories]

    def create_category(self, group_id: UUID, user_id: UUID, name: str) -> ShoppingCategorySummary:
        self._lock_membership(group_id, user_id)
        normalized_name = name.strip()
        if self._category_by_name(group_id, normalized_name) is not None:
            raise ShoppingCategoryDuplicateError
        last_order = self._session.scalar(
            select(func.max(ShoppingCategory.sort_order)).where(ShoppingCategory.group_id == group_id)
        )
        category = ShoppingCategory(
            id=uuid4(),
            group_id=group_id,
            name=normalized_name,
            sort_order=int(last_order if last_order is not None else -1) + 1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._session.add(category)
        self._commit("Could not create shopping category")
        return self._category_summary(category)

    def update_category(self, category_id: UUID, user_id: UUID, name: str) -> ShoppingCategorySummary:
        group_id = self._category_group_id(category_id)
        self._lock_membership(group_id, user_id)
        category = self._locked_category(category_id)
        normalized_name = name.strip()
        existing = self._category_by_name(group_id, normalized_name)
        if existing is not None and existing.id != category_id:
            raise ShoppingCategoryDuplicateError
        category.name = normalized_name
        category.updated_at = datetime.now(UTC)
        self._commit("Could not update shopping category")
        return self._category_summary(category)

    def delete_category(self, category_id: UUID, user_id: UUID) -> None:
        group_id = self._category_group_id(category_id)
        self._lock_membership(group_id, user_id)
        category = self._locked_category(category_id)
        if self._session.scalar(
            select(func.count()).select_from(ShoppingItem).where(ShoppingItem.category_id == category_id)
        ):
            raise ShoppingCategoryInUseError
        self._session.delete(category)
        self._commit("Could not delete shopping category")

    def reorder_categories(
        self, group_id: UUID, user_id: UUID, category_ids: list[UUID]
    ) -> list[ShoppingCategorySummary]:
        self._lock_membership(group_id, user_id)
        categories = list(
            self._session.scalars(
                select(ShoppingCategory)
                .where(ShoppingCategory.group_id == group_id)
                .order_by(ShoppingCategory.sort_order.asc(), ShoppingCategory.id.asc())
                .with_for_update()
            ).all()
        )
        category_by_id = {category.id: category for category in categories}
        if len(category_ids) != len(categories) or len(set(category_ids)) != len(category_ids):
            raise ShoppingWorkflowConflictError
        if set(category_ids) != set(category_by_id):
            raise ShoppingWorkflowConflictError
        now = datetime.now(UTC)
        for sort_order, category_id in enumerate(category_ids):
            category_by_id[category_id].sort_order = sort_order
            category_by_id[category_id].updated_at = now
        self._commit("Could not reorder shopping categories")
        return [self._category_summary(category_by_id[category_id]) for category_id in category_ids]

    def start_trip(self, group_id: UUID, user_id: UUID) -> ShoppingTripSummary:
        self._lock_membership(group_id, user_id)
        trip = self._new_trip(group_id, user_id)
        self._commit("Could not start shopping trip")
        return self._trip_summary(trip, [])

    def purchase_item(self, item_id: UUID, user_id: UUID, trip_id: UUID | None = None) -> ShoppingPurchaseSummary:
        group_id = self._item_group_id(item_id)
        self._lock_membership(group_id, user_id)
        item = self._locked_item(item_id)
        if item.group_id != group_id:
            raise ShoppingWorkflowNotFoundError
        if item.purchased_at is not None:
            raise ShoppingWorkflowConflictError
        trip = self._resolve_trip(group_id, user_id, trip_id)
        if trip.finalized_at is not None:
            raise ShoppingWorkflowConflictError
        now = datetime.now(UTC)
        assignee_username = self._username(item.assignee_user_id)
        category_name = self._category_name(item.category_id)
        purchase = ShoppingPurchase(
            id=uuid4(),
            group_id=group_id,
            trip_id=trip.id,
            shopping_item_id=item.id,
            item_name_snapshot=item.name,
            assignee_user_id=item.assignee_user_id,
            assignee_username_snapshot=assignee_username,
            category_id=item.category_id,
            category_name_snapshot=category_name,
            purchased_by_user_id=user_id,
            purchased_at=now,
            updated_at=now,
        )
        self._session.add(purchase)
        item.purchased_by_user_id = user_id
        item.purchased_at = now
        item.updated_at = now
        self._commit("Could not purchase shopping item")
        return self._purchase_summary(purchase)

    def restore_item(self, item_id: UUID, user_id: UUID) -> ShoppingPurchaseSummary | None:
        group_id = self._item_group_id(item_id)
        self._lock_membership(group_id, user_id)
        item = self._locked_item(item_id)
        purchase = self._session.scalar(
            select(ShoppingPurchase)
            .where(ShoppingPurchase.shopping_item_id == item_id, ShoppingPurchase.reversed_at.is_(None))
            .order_by(ShoppingPurchase.purchased_at.desc(), ShoppingPurchase.id.desc())
            .with_for_update()
        )
        if purchase is None and item.purchased_at is None:
            raise ShoppingWorkflowConflictError
        now = datetime.now(UTC)
        if purchase is not None:
            purchase.reversed_at = now
            purchase.reversed_by_user_id = user_id
            purchase.updated_at = now
        self._sync_item_purchase_state(item)
        item.updated_at = now
        self._commit("Could not restore shopping item")
        return self._purchase_summary(purchase) if purchase is not None else None

    def list_trips(
        self, group_id: UUID, user_id: UUID, cursor: str | None, limit: int = 20
    ) -> tuple[list[ShoppingTripSummary], str | None]:
        self._require_membership(group_id, user_id)
        statement = select(ShoppingTrip).where(ShoppingTrip.group_id == group_id)
        if cursor:
            cursor_started_at, cursor_id = self._decode_cursor(cursor)
            statement = statement.where(
                or_(
                    ShoppingTrip.started_at < cursor_started_at,
                    and_(ShoppingTrip.started_at == cursor_started_at, ShoppingTrip.id < cursor_id),
                )
            )
        trips = list(
            self._session.scalars(
                statement.order_by(ShoppingTrip.started_at.desc(), ShoppingTrip.id.desc()).limit(limit + 1)
            ).all()
        )
        next_cursor = None
        if len(trips) > limit:
            last = trips.pop()
            next_cursor = self._encode_cursor(last.started_at, last.id)
        return [self._trip_summary(trip, self._trip_purchases(trip.id)) for trip in trips], next_cursor

    def get_trip(self, trip_id: UUID, user_id: UUID) -> ShoppingTripSummary:
        trip = self._session.get(ShoppingTrip, trip_id)
        if trip is None:
            raise ShoppingWorkflowNotFoundError
        self._require_membership(trip.group_id, user_id)
        return self._trip_summary(trip, self._trip_purchases(trip.id))

    def update_trip(
        self, trip_id: UUID, user_id: UUID, total_amount_yen: int | None, finalize: bool
    ) -> ShoppingTripSummary:
        group_id = self._trip_group_id(trip_id)
        self._lock_membership(group_id, user_id)
        trip = self._locked_trip(trip_id)
        trip.total_amount_yen = total_amount_yen
        if finalize and trip.finalized_at is None:
            trip.finalized_at = datetime.now(UTC)
        if finalize:
            trip.recorded_by_user_id = user_id
        trip.updated_at = datetime.now(UTC)
        self._commit("Could not update shopping trip")
        return self._trip_summary(trip, self._trip_purchases(trip.id))

    def add_unplanned_purchase(
        self,
        trip_id: UUID,
        user_id: UUID,
        name: str,
        category_id: UUID | None,
        purchased_by_user_id: UUID | None,
    ) -> ShoppingPurchaseSummary:
        group_id = self._trip_group_id(trip_id)
        self._lock_membership(group_id, user_id)
        trip = self._locked_trip(trip_id)
        self._validate_category(trip.group_id, category_id)
        purchaser_id = purchased_by_user_id or user_id
        self._validate_membership(trip.group_id, purchaser_id)
        now = datetime.now(UTC)
        purchase = ShoppingPurchase(
            id=uuid4(),
            group_id=trip.group_id,
            trip_id=trip.id,
            shopping_item_id=None,
            item_name_snapshot=name.strip(),
            category_id=category_id,
            category_name_snapshot=self._category_name(category_id),
            purchased_by_user_id=purchaser_id,
            purchased_at=now,
            updated_at=now,
        )
        self._session.add(purchase)
        self._commit("Could not add unplanned shopping purchase")
        return self._purchase_summary(purchase)

    def update_purchase(
        self,
        purchase_id: UUID,
        user_id: UUID,
        category_id: UUID | None,
        purchased_by_user_id: UUID | None,
    ) -> ShoppingPurchaseSummary:
        group_id = self._purchase_group_id(purchase_id)
        self._lock_membership(group_id, user_id)
        purchase = self._locked_purchase(purchase_id)
        self._validate_category(purchase.group_id, category_id)
        self._validate_membership(purchase.group_id, purchased_by_user_id or purchase.purchased_by_user_id)
        purchase.category_id = category_id
        purchase.category_name_snapshot = self._category_name(category_id)
        purchase.purchased_by_user_id = purchased_by_user_id or purchase.purchased_by_user_id
        purchase.updated_at = datetime.now(UTC)
        self._commit("Could not update shopping purchase")
        return self._purchase_summary(purchase)

    def reverse_purchase(self, purchase_id: UUID, user_id: UUID) -> ShoppingPurchaseSummary:
        group_id = self._purchase_group_id(purchase_id)
        self._lock_membership(group_id, user_id)
        purchase = self._locked_purchase(purchase_id)
        if purchase.reversed_at is not None:
            raise ShoppingWorkflowConflictError
        if purchase.shopping_item_id is not None:
            item = self._locked_item(purchase.shopping_item_id)
            purchase.reversed_at = datetime.now(UTC)
            purchase.reversed_by_user_id = user_id
            self._sync_item_purchase_state(item)
            item.updated_at = datetime.now(UTC)
        else:
            purchase.reversed_at = datetime.now(UTC)
            purchase.reversed_by_user_id = user_id
        purchase.updated_at = datetime.now(UTC)
        self._commit("Could not reverse shopping purchase")
        return self._purchase_summary(purchase)

    def statistics(self, group_id: UUID, user_id: UUID, from_date: date, to_date: date) -> dict[str, object]:
        self._require_membership(group_id, user_id)
        if from_date > to_date:
            raise ShoppingInvalidDateRangeError
        group = self._session.get(FamilyGroup, group_id)
        if group is None:
            raise ShoppingWorkflowNotFoundError
        timezone = ZoneInfo(group.timezone)
        start = datetime.combine(from_date, time.min, tzinfo=timezone).astimezone(UTC)
        end = datetime.combine(to_date, time.max, tzinfo=timezone).astimezone(UTC)
        trips = list(
            self._session.scalars(
                select(ShoppingTrip).where(
                    ShoppingTrip.group_id == group_id,
                    ShoppingTrip.started_at >= start,
                    ShoppingTrip.started_at <= end,
                )
            ).all()
        )
        purchases = list(
            self._session.scalars(
                select(ShoppingPurchase).where(
                    ShoppingPurchase.group_id == group_id,
                    ShoppingPurchase.purchased_at >= start,
                    ShoppingPurchase.purchased_at <= end,
                    ShoppingPurchase.reversed_at.is_(None),
                )
            ).all()
        )
        users = self._user_directory.list_by_ids(
            {purchase.purchased_by_user_id for purchase in purchases}
            | {purchase.assignee_user_id for purchase in purchases if purchase.assignee_user_id is not None}
        )
        purchaser_counts: dict[str, int] = {}
        assignee_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        monthly: dict[str, int] = {}
        for purchase in purchases:
            purchaser = users.get(purchase.purchased_by_user_id)
            purchaser_name = purchaser.username if purchaser else "unknown"
            purchaser_counts[purchaser_name] = purchaser_counts.get(purchaser_name, 0) + 1
            if purchase.assignee_user_id is not None:
                assignee = users.get(purchase.assignee_user_id)
                assignee_name = assignee.username if assignee else purchase.assignee_username_snapshot or "unknown"
                assignee_counts[assignee_name] = assignee_counts.get(assignee_name, 0) + 1
            category_name = purchase.category_name_snapshot or "Uncategorized"
            category_counts[category_name] = category_counts.get(category_name, 0) + 1
        for trip in trips:
            if trip.total_amount_yen is not None:
                month = trip.started_at.astimezone(timezone).strftime("%Y-%m")
                monthly[month] = monthly.get(month, 0) + trip.total_amount_yen
        return {
            "group_id": group_id,
            "from_date": from_date,
            "to_date": to_date,
            "total_amount_yen": sum(trip.total_amount_yen or 0 for trip in trips),
            "unrecorded_trip_count": sum(trip.total_amount_yen is None for trip in trips),
            "trip_count": len(trips),
            "purchase_count": len(purchases),
            "planned_purchase_count": sum(purchase.shopping_item_id is not None for purchase in purchases),
            "unplanned_purchase_count": sum(purchase.shopping_item_id is None for purchase in purchases),
            "purchasers": [{"username": name, "count": count} for name, count in sorted(purchaser_counts.items())],
            "assignees": [{"username": name, "count": count} for name, count in sorted(assignee_counts.items())],
            "categories": [{"name": name, "count": count} for name, count in sorted(category_counts.items())],
            "monthly": [{"month": month, "amount_yen": amount} for month, amount in sorted(monthly.items())],
        }

    def _new_trip(self, group_id: UUID, user_id: UUID) -> ShoppingTrip:
        now = datetime.now(UTC)
        trip = ShoppingTrip(
            id=uuid4(),
            group_id=group_id,
            started_by_user_id=user_id,
            started_at=now,
            updated_at=now,
        )
        self._session.add(trip)
        return trip

    def _resolve_trip(self, group_id: UUID, user_id: UUID, trip_id: UUID | None) -> ShoppingTrip:
        if trip_id is not None:
            trip = self._locked_trip(trip_id)
            if trip.group_id != group_id:
                raise ShoppingWorkflowNotFoundError
            return trip
        trip = self._session.scalar(
            select(ShoppingTrip)
            .where(
                ShoppingTrip.group_id == group_id,
                ShoppingTrip.finalized_at.is_(None),
            )
            .order_by(ShoppingTrip.started_at.desc(), ShoppingTrip.id.desc())
            .limit(1)
            .with_for_update()
        )
        return trip or self._new_trip(group_id, user_id)

    def _trip_purchases(self, trip_id: UUID) -> list[ShoppingPurchase]:
        return list(
            self._session.scalars(
                select(ShoppingPurchase)
                .where(ShoppingPurchase.trip_id == trip_id)
                .order_by(ShoppingPurchase.purchased_at.asc(), ShoppingPurchase.id.asc())
            ).all()
        )

    def _trip_summary(self, trip: ShoppingTrip, purchases: list[ShoppingPurchase]) -> ShoppingTripSummary:
        ids = {trip.started_by_user_id}
        if trip.recorded_by_user_id is not None:
            ids.add(trip.recorded_by_user_id)
        ids.update(purchase.purchased_by_user_id for purchase in purchases)
        users = self._user_directory.list_by_ids(ids)
        started_by = users.get(trip.started_by_user_id)
        recorded_by = users.get(trip.recorded_by_user_id) if trip.recorded_by_user_id else None
        return ShoppingTripSummary(
            id=trip.id,
            group_id=trip.group_id,
            started_by_user_id=trip.started_by_user_id,
            started_by_username=started_by.username if started_by else "unknown",
            started_at=trip.started_at,
            finalized_at=trip.finalized_at,
            total_amount_yen=trip.total_amount_yen,
            recorded_by_user_id=trip.recorded_by_user_id,
            recorded_by_username=recorded_by.username if recorded_by else None,
            updated_at=trip.updated_at,
            purchase_count=len(purchases),
            active_purchase_count=sum(purchase.reversed_at is None for purchase in purchases),
            purchases=[self._purchase_summary(purchase) for purchase in purchases],
        )

    def _purchase_summary(self, purchase: ShoppingPurchase) -> ShoppingPurchaseSummary:
        purchaser = self._user_directory.list_by_ids({purchase.purchased_by_user_id}).get(purchase.purchased_by_user_id)
        return ShoppingPurchaseSummary(
            id=purchase.id,
            trip_id=purchase.trip_id,
            shopping_item_id=purchase.shopping_item_id,
            item_name=purchase.item_name_snapshot,
            assignee_user_id=purchase.assignee_user_id,
            assignee_username=purchase.assignee_username_snapshot,
            category_id=purchase.category_id,
            category_name=purchase.category_name_snapshot,
            purchased_by_user_id=purchase.purchased_by_user_id,
            purchased_by_username=purchaser.username if purchaser else "unknown",
            purchased_at=purchase.purchased_at,
            reversed_at=purchase.reversed_at,
            reversed_by_user_id=purchase.reversed_by_user_id,
        )

    def _item_summaries(self, items: list[ShoppingItem]) -> list[ShoppingListItemSummary]:
        user_ids = {item.created_by_user_id for item in items}
        user_ids.update(item.assignee_user_id for item in items if item.assignee_user_id is not None)
        users = self._user_directory.list_by_ids(user_ids)
        category_ids = {item.category_id for item in items if item.category_id is not None}
        categories = (
            {
                category.id: category
                for category in self._session.scalars(
                    select(ShoppingCategory).where(ShoppingCategory.id.in_(category_ids))
                ).all()
            }
            if category_ids
            else {}
        )
        return [
            ShoppingListItemSummary(
                id=item.id,
                group_id=item.group_id,
                name=item.name,
                created_by_user_id=item.created_by_user_id,
                created_at=item.created_at,
                updated_at=item.updated_at,
                assignee_user_id=item.assignee_user_id,
                assignee_username=users[item.assignee_user_id].username
                if item.assignee_user_id is not None and item.assignee_user_id in users
                else None,
                category_id=item.category_id,
                category_name=categories[item.category_id].name
                if item.category_id is not None and item.category_id in categories
                else None,
            )
            for item in items
        ]

    def _validate_assignment(self, group_id: UUID, user_id: UUID | None) -> None:
        if user_id is not None:
            self._validate_membership(group_id, user_id)

    def _validate_category(self, group_id: UUID, category_id: UUID | None) -> None:
        if (
            category_id is not None
            and self._session.scalar(
                select(ShoppingCategory.id).where(
                    ShoppingCategory.id == category_id, ShoppingCategory.group_id == group_id
                )
            )
            is None
        ):
            raise ShoppingWorkflowNotFoundError

    def _validate_membership(self, group_id: UUID, user_id: UUID) -> None:
        if self._session.get(FamilyGroupMember, (group_id, user_id)) is None:
            raise ShoppingWorkflowNotFoundError

    def _require_membership(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        membership = self._session.get(FamilyGroupMember, (group_id, user_id))
        if membership is None:
            raise ShoppingWorkflowNotFoundError
        return membership

    def _lock_membership(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        if group_id not in lock_user_group_ids(self._session, user_id, {group_id}):
            raise ShoppingWorkflowNotFoundError
        return self._require_membership(group_id, user_id)

    def _item_group_id(self, item_id: UUID) -> UUID:
        group_id = self._session.scalar(select(ShoppingItem.group_id).where(ShoppingItem.id == item_id))
        if group_id is None:
            raise ShoppingWorkflowNotFoundError
        return group_id

    def _trip_group_id(self, trip_id: UUID) -> UUID:
        group_id = self._session.scalar(select(ShoppingTrip.group_id).where(ShoppingTrip.id == trip_id))
        if group_id is None:
            raise ShoppingWorkflowNotFoundError
        return group_id

    def _purchase_group_id(self, purchase_id: UUID) -> UUID:
        group_id = self._session.scalar(select(ShoppingPurchase.group_id).where(ShoppingPurchase.id == purchase_id))
        if group_id is None:
            raise ShoppingWorkflowNotFoundError
        return group_id

    def _category_group_id(self, category_id: UUID) -> UUID:
        group_id = self._session.scalar(select(ShoppingCategory.group_id).where(ShoppingCategory.id == category_id))
        if group_id is None:
            raise ShoppingWorkflowNotFoundError
        return group_id

    def _locked_item(self, item_id: UUID) -> ShoppingItem:
        item = self._session.scalar(select(ShoppingItem).where(ShoppingItem.id == item_id).with_for_update())
        if item is None:
            raise ShoppingWorkflowNotFoundError
        return item

    def _sync_item_purchase_state(self, item: ShoppingItem) -> None:
        latest_purchase = self._session.scalar(
            select(ShoppingPurchase)
            .where(
                ShoppingPurchase.shopping_item_id == item.id,
                ShoppingPurchase.reversed_at.is_(None),
            )
            .order_by(ShoppingPurchase.purchased_at.desc(), ShoppingPurchase.id.desc())
            .limit(1)
        )
        if latest_purchase is None:
            item.purchased_by_user_id = None
            item.purchased_at = None
        else:
            item.purchased_by_user_id = latest_purchase.purchased_by_user_id
            item.purchased_at = latest_purchase.purchased_at

    def _locked_category(self, category_id: UUID) -> ShoppingCategory:
        category = self._session.scalar(
            select(ShoppingCategory).where(ShoppingCategory.id == category_id).with_for_update()
        )
        if category is None:
            raise ShoppingWorkflowNotFoundError
        return category

    def _locked_trip(self, trip_id: UUID) -> ShoppingTrip:
        trip = self._session.scalar(select(ShoppingTrip).where(ShoppingTrip.id == trip_id).with_for_update())
        if trip is None:
            raise ShoppingWorkflowNotFoundError
        return trip

    def _locked_purchase(self, purchase_id: UUID) -> ShoppingPurchase:
        purchase = self._session.scalar(
            select(ShoppingPurchase).where(ShoppingPurchase.id == purchase_id).with_for_update()
        )
        if purchase is None:
            raise ShoppingWorkflowNotFoundError
        return purchase

    def _category_by_name(self, group_id: UUID, name: str) -> ShoppingCategory | None:
        return self._session.scalar(
            select(ShoppingCategory).where(
                ShoppingCategory.group_id == group_id,
                func.lower(ShoppingCategory.name) == name.lower(),
            )
        )

    def _category_name(self, category_id: UUID | None) -> str | None:
        if category_id is None:
            return None
        category = self._session.get(ShoppingCategory, category_id)
        return category.name if category else None

    def _username(self, user_id: UUID | None) -> str | None:
        if user_id is None:
            return None
        user = self._user_directory.list_by_ids({user_id}).get(user_id)
        return user.username if user else None

    @staticmethod
    def _category_summary(category: ShoppingCategory) -> ShoppingCategorySummary:
        return ShoppingCategorySummary(
            id=category.id,
            group_id=category.group_id,
            name=category.name,
            sort_order=category.sort_order,
            created_at=category.created_at,
            updated_at=category.updated_at,
        )

    @staticmethod
    def _encode_cursor(started_at: datetime, trip_id: UUID) -> str:
        value = json.dumps({"started_at": started_at.isoformat(), "id": str(trip_id)}).encode()
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            value = json.loads(base64.urlsafe_b64decode(padded).decode())
            return datetime.fromisoformat(value["started_at"]), UUID(value["id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ShoppingInvalidCursorError from error

    def _commit(self, message: str) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise ShoppingWorkflowPersistenceError(message) from error
