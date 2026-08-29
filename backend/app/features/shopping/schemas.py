from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ShoppingItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("shopping item name must not be blank")
        return normalized


class ShoppingItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    name: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    purchased_by_user_id: UUID | None
    purchased_by_username: str | None
    purchased_at: datetime | None

    @field_validator("created_at", "updated_at", "purchased_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("shopping item datetime must be timezone-aware")
        return value.astimezone(UTC)


class ShoppingItemListResponse(BaseModel):
    items: list[ShoppingItemResponse]


class ShoppingCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("shopping category name must not be blank")
        return normalized


class ShoppingCategoryUpdate(ShoppingCategoryCreate):
    pass


class ShoppingCategoryOrderUpdate(BaseModel):
    category_ids: list[UUID]


class ShoppingCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_category_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("shopping category datetime must be timezone-aware")
        return value.astimezone(UTC)


class ShoppingCategoryListResponse(BaseModel):
    items: list[ShoppingCategoryResponse]


class ShoppingItemUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    assignee_user_id: UUID | None = None
    category_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def normalize_item_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("shopping item name must not be blank")
        return normalized


class ShoppingItemCreateDetailed(ShoppingItemCreate):
    assignee_user_id: UUID | None = None
    category_id: UUID | None = None


class ShoppingListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_list_item_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("shopping item datetime must be timezone-aware")
        return value.astimezone(UTC)


class ShoppingListItemListResponse(BaseModel):
    items: list[ShoppingListItemResponse]


class ShoppingTripStart(BaseModel):
    pass


class ShoppingTripUpdate(BaseModel):
    total_amount_yen: int | None = Field(default=None, ge=0)
    finalize: bool = True
    delete_if_empty: bool = False


class ShoppingPurchaseResponse(BaseModel):
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

    @field_validator("purchased_at", "reversed_at")
    @classmethod
    def normalize_purchase_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("shopping purchase datetime must be timezone-aware")
        return value.astimezone(UTC)


class ShoppingTripResponse(BaseModel):
    id: UUID
    group_id: UUID
    started_by_user_id: UUID
    started_by_username: str
    started_at: datetime
    finalized_at: datetime | None
    discarded_at: datetime | None
    discarded_by_user_id: UUID | None
    discarded_by_username: str | None
    total_amount_yen: int | None
    recorded_by_user_id: UUID | None
    recorded_by_username: str | None
    updated_at: datetime
    purchase_count: int
    active_purchase_count: int
    purchases: list[ShoppingPurchaseResponse] = Field(default_factory=list)

    @field_validator("started_at", "finalized_at", "discarded_at", "updated_at")
    @classmethod
    def normalize_trip_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("shopping trip datetime must be timezone-aware")
        return value.astimezone(UTC)


class ShoppingTripListResponse(BaseModel):
    items: list[ShoppingTripResponse]
    next_cursor: str | None


class ShoppingUnplannedPurchaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category_id: UUID | None = None
    purchased_by_user_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def normalize_unplanned_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("shopping purchase name must not be blank")
        return normalized


class ShoppingPurchaseUpdate(BaseModel):
    category_id: UUID | None = None
    purchased_by_user_id: UUID = Field(default=None)


class ShoppingStatisticsResponse(BaseModel):
    group_id: UUID
    from_date: date
    to_date: date
    total_amount_yen: int
    unrecorded_trip_count: int
    trip_count: int
    purchase_count: int
    planned_purchase_count: int
    unplanned_purchase_count: int
    purchasers: list[dict[str, object]]
    assignees: list[dict[str, object]]
    categories: list[dict[str, object]]
    monthly: list[dict[str, object]]
