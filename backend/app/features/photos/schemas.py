from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.features.photos.models import (
    PhotoActivityEventType,
    PhotoLifecycleState,
    PhotoVisibility,
    UploadBatchStatus,
    UploadItemStatus,
)
from app.features.photos.storage import StorageStatusCode


class StorageStatusResponse(BaseModel):
    status: StorageStatusCode
    available: bool
    writable: bool
    free_bytes: int | None
    minimum_free_bytes: int | None
    total_bytes: int | None


class PhotoSharing(BaseModel):
    type: PhotoVisibility
    group_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("group_ids")
    @classmethod
    def require_unique_group_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("group_ids must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> "PhotoSharing":
        if self.type is PhotoVisibility.PRIVATE and self.group_ids:
            raise ValueError("private sharing must not include groups")
        if self.type is PhotoVisibility.SHARED and not self.group_ids:
            raise ValueError("shared photos require at least one group")
        return self


class PhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uploaded_by_user_id: UUID
    uploaded_by_username: str
    visibility: PhotoVisibility
    sharing: PhotoSharing
    memo: str | None
    memo_updated_by_user_id: UUID
    memo_updated_by_username: str
    memo_updated_at: datetime
    metadata_version: int
    is_favorite: bool
    original_filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    sha256: str
    width: int | None
    height: int | None
    captured_at: datetime | None
    uploaded_at: datetime
    lifecycle_state: PhotoLifecycleState
    trashed_at: datetime | None
    purge_after: datetime | None
    purge_requested_at: datetime | None
    captured_at_original: datetime | None = None
    captured_at_override: datetime | None = None

    @field_validator(
        "captured_at",
        "captured_at_original",
        "captured_at_override",
        "uploaded_at",
        "memo_updated_at",
        "trashed_at",
        "purge_after",
        "purge_requested_at",
    )
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("photo datetimes must be timezone-aware")
        return value.astimezone(UTC)


class TrashedPhotoListResponse(BaseModel):
    items: list[PhotoResponse]
    next_cursor: str | None
    total_count: int


class PhotoListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uploaded_by_user_id: UUID
    uploaded_by_username: str
    visibility: PhotoVisibility
    original_filename: str
    content_type: str
    width: int | None
    height: int | None
    captured_at: datetime | None
    uploaded_at: datetime
    is_favorite: bool

    @field_validator("captured_at", "uploaded_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("photo datetimes must be timezone-aware")
        return value.astimezone(UTC)


class PhotoListResponse(BaseModel):
    items: list[PhotoListItemResponse]
    next_cursor: str | None
    total_count: int


class PhotoActivityItemResponse(BaseModel):
    id: UUID
    event_type: PhotoActivityEventType
    actor_user_id: UUID
    actor_username: str
    operation_id: UUID
    occurred_at: datetime
    photo: PhotoListItemResponse

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("activity datetimes must be timezone-aware")
        return value.astimezone(UTC)


class PhotoActivityResponse(BaseModel):
    items: list[PhotoActivityItemResponse]
    next_cursor: str | None
    unseen_count: int = Field(ge=0)


class PhotoActivitySeenUpdate(BaseModel):
    event_id: UUID


class PhotoTimelineMonthResponse(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    count: int = Field(ge=0)


class PhotoTimelineResponse(BaseModel):
    year: int
    months: list[PhotoTimelineMonthResponse]


class PhotoListQuery(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=512)
    q: str | None = Field(default=None, max_length=100)
    date_from: date | None = None
    date_to: date | None = None
    uploader_id: UUID | None = None
    mine_only: bool = False
    visibility: PhotoVisibility | None = None
    captured_at_known: bool | None = None
    album_id: UUID | None = None
    exclude_album_id: UUID | None = None
    sharing_group_id: UUID | None = None
    favorite: bool | None = None

    @field_validator("q")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_dates(self) -> "PhotoListQuery":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        if self.mine_only and self.uploader_id:
            raise ValueError("mine_only and uploader_id cannot be combined")
        if self.album_id and self.exclude_album_id:
            raise ValueError("album_id and exclude_album_id cannot be combined")
        return self


class PhotoUpdate(BaseModel):
    memo: str | None = Field(default=None, max_length=2000)
    sharing: PhotoSharing | None = None
    captured_at_override: datetime | None = None
    version: int = Field(gt=0)

    @field_validator("memo")
    @classmethod
    def normalize_memo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("captured_at_override")
    @classmethod
    def require_timezone_for_capture_override(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("captured_at_override must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "PhotoUpdate":
        if (
            "memo" not in self.model_fields_set
            and self.sharing is None
            and "captured_at_override" not in self.model_fields_set
        ):
            raise ValueError("memo, sharing, or captured_at_override must be provided")
        return self


class GroupPhotoModerationRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class BulkPhotoSharingAdd(BaseModel):
    photo_ids: list[UUID] = Field(min_length=1, max_length=100)
    add_group_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("photo_ids", "add_group_ids")
    @classmethod
    def require_unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("identifiers must not contain duplicates")
        return value


class PhotoExportRequest(BaseModel):
    photo_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("photo_ids")
    @classmethod
    def require_unique_photo_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("photo_ids must not contain duplicates")
        return value


class BulkPhotoSharingResponse(BaseModel):
    operation_id: UUID
    updated_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)


class UploadFileCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1, max_length=1024)
    content_type: str = Field(min_length=1, max_length=64)
    size_bytes: int = Field(gt=0)


class UploadBatchCreate(BaseModel):
    sharing: PhotoSharing = Field(default_factory=lambda: PhotoSharing(type=PhotoVisibility.PRIVATE))
    files: list[UploadFileCreate] = Field(min_length=1, max_length=100)


class UploadItemResponse(BaseModel):
    id: UUID
    client_id: str
    filename: str
    content_type: str
    size_bytes: int
    received_bytes: int
    status: UploadItemStatus
    error_code: str | None
    photo_id: UUID | None


class UploadBatchResponse(BaseModel):
    id: UUID
    status: UploadBatchStatus
    visibility: PhotoVisibility
    group_ids: list[UUID]
    created_at: datetime
    expires_at: datetime
    completed_at: datetime | None
    items: list[UploadItemResponse]
