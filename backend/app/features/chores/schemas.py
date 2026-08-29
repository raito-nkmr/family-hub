from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.features.groups.public import GroupRole


def _normalize_category_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("chore category name must not be blank")
    return normalized


class ChoreCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_category_name(value)


class ChoreCategoryUpdate(ChoreCategoryCreate):
    pass


class ChoreCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("chore category datetime must be timezone-aware")
        return value.astimezone(UTC)


class ChoreCategoryListResponse(BaseModel):
    items: list[ChoreCategoryResponse]


class ChoreCategoryOrderUpdate(BaseModel):
    category_ids: list[UUID]


class ChoreTaskCreate(BaseModel):
    task_name: str = Field(min_length=1, max_length=120)
    category_id: UUID
    interval_days: int = Field(ge=1, le=3650)

    @field_validator("task_name")
    @classmethod
    def normalize_task_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("chore task name must not be blank")
        return normalized


class ChoreTaskUpdate(BaseModel):
    task_name: str | None = Field(default=None, min_length=1, max_length=120)
    category_id: UUID | None = None
    interval_days: int | None = Field(default=None, ge=1, le=3650)
    is_active: bool | None = None

    @field_validator("task_name")
    @classmethod
    def normalize_task_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("chore task name must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> "ChoreTaskUpdate":
        if (
            self.task_name is None
            and self.category_id is None
            and self.interval_days is None
            and self.is_active is None
        ):
            raise ValueError("at least one chore task field must be provided")
        return self


class ChoreCompletionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    completed_by_user_id: UUID
    completed_by_username: str
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("chore completion datetime must be timezone-aware")
        return value.astimezone(UTC)


class ChoreTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    task_name: str
    category_id: UUID
    interval_days: int
    is_active: bool
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    next_due_at: datetime
    current_user_role: GroupRole
    last_completion: ChoreCompletionResponse | None

    @field_validator("created_at", "updated_at", "next_due_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("chore task datetime must be timezone-aware")
        return value.astimezone(UTC)


class ChoreTaskListResponse(BaseModel):
    items: list[ChoreTaskResponse]


class ChoreMonthlySummaryResponse(BaseModel):
    completion_count: int
    unique_task_count: int
    participant_count: int
    category_count: int


class ChoreMonthlyDailyResponse(BaseModel):
    day: date
    completion_count: int
    unique_task_count: int


class ChoreMonthlyCategoryResponse(BaseModel):
    category_id: UUID | None
    name: str
    completion_count: int
    unique_task_count: int


class ChoreMonthlyMemberResponse(BaseModel):
    user_id: UUID
    username: str
    completion_count: int
    unique_task_count: int
    completion_ratio: float


class ChoreMonthlyTaskMemberResponse(BaseModel):
    user_id: UUID
    username: str
    completion_count: int


class ChoreMonthlyTaskResponse(BaseModel):
    task_id: UUID
    task_name: str
    category_id: UUID | None
    category_name: str
    completion_count: int
    participant_count: int
    members: list[ChoreMonthlyTaskMemberResponse]


class ChoreMonthlyReportResponse(BaseModel):
    group_id: UUID
    month: str
    timezone: str
    summary: ChoreMonthlySummaryResponse
    daily: list[ChoreMonthlyDailyResponse]
    categories: list[ChoreMonthlyCategoryResponse]
    members: list[ChoreMonthlyMemberResponse]
    tasks: list[ChoreMonthlyTaskResponse]
