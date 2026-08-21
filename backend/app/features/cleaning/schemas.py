from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.features.groups.public import GroupRole


def _normalize_category_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("cleaning category name must not be blank")
    return normalized


class CleaningCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_category_name(value)


class CleaningCategoryUpdate(CleaningCategoryCreate):
    pass


class CleaningCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("cleaning category datetime must be timezone-aware")
        return value.astimezone(UTC)


class CleaningCategoryListResponse(BaseModel):
    items: list[CleaningCategoryResponse]


class CleaningTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category_id: UUID
    interval_days: int = Field(ge=1, le=3650)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("cleaning task name must not be blank")
        return normalized


class CleaningTaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category_id: UUID | None = None
    interval_days: int | None = Field(default=None, ge=1, le=3650)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("cleaning task name must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> "CleaningTaskUpdate":
        if self.name is None and self.category_id is None and self.interval_days is None and self.is_active is None:
            raise ValueError("at least one cleaning task field must be provided")
        return self


class CleaningCompletionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    completed_by_user_id: UUID
    completed_by_username: str
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("cleaning completion datetime must be timezone-aware")
        return value.astimezone(UTC)


class CleaningTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    name: str
    category_id: UUID
    interval_days: int
    is_active: bool
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    next_due_at: datetime
    current_user_role: GroupRole
    last_completion: CleaningCompletionResponse | None

    @field_validator("created_at", "updated_at", "next_due_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("cleaning task datetime must be timezone-aware")
        return value.astimezone(UTC)


class CleaningTaskListResponse(BaseModel):
    items: list[CleaningTaskResponse]
