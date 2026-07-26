from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.features.photos.public import PhotoResponse


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class AlbumCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    group_id: UUID

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("album title must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class AlbumUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    cover_photo_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("album title must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "AlbumUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one album field must be provided")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("album title must not be null")
        return self


class AlbumPhotoAdd(BaseModel):
    photo_ids: list[UUID] = Field(min_length=1, max_length=200)

    @field_validator("photo_ids")
    @classmethod
    def require_unique_photo_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("photo_ids must not contain duplicates")
        return value


class AlbumResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    created_by_user_id: UUID
    created_by_username: str
    group_id: UUID
    group_name: str | None
    cover_photo_id: UUID | None
    created_at: datetime
    updated_at: datetime
    photo_count: int

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("album datetimes must be timezone-aware")
        return value.astimezone(UTC)


class AlbumDetailResponse(AlbumResponse):
    photos: list[PhotoResponse]
    next_cursor: str | None


class AlbumListResponse(BaseModel):
    items: list[AlbumResponse]
