from datetime import UTC, datetime
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
