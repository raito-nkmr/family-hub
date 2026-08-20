from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.groups.models import GroupRole


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("group name must not be blank")
        return normalized


class GroupMemberRoleUpdate(BaseModel):
    role: GroupRole


class GroupUpdate(GroupCreate):
    pass


class GroupMemberRemovalImpactResponse(BaseModel):
    user_id: UUID
    username: str
    shared_photo_count: int
    created_album_count: int
    created_cleaning_task_count: int
    created_shopping_item_count: int


class GroupAdministrationOverviewResponse(BaseModel):
    album_count: int
    shared_photo_count: int
    cleaning_task_count: int
    shopping_item_count: int
    active_admin_count: int


class GroupMembershipInvitationCreate(BaseModel):
    user_id: UUID
    role: GroupRole = GroupRole.MEMBER


class GroupMembershipInvitationResponse(BaseModel):
    id: UUID
    group_id: UUID
    group_name: str
    user_id: UUID
    username: str
    role: GroupRole
    status: str
    created_at: datetime


class GroupMembershipInvitationListResponse(BaseModel):
    items: list[GroupMembershipInvitationResponse]


class GroupMembershipInvitationDecision(BaseModel):
    accept: bool


class GroupAuditEventResponse(BaseModel):
    id: UUID
    action: str
    actor_username: str
    target_type: str
    target_id: str
    details: dict[str, object]
    created_at: datetime


class GroupAuditEventListResponse(BaseModel):
    items: list[GroupAuditEventResponse]


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    current_user_role: GroupRole
    member_count: int

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("group datetimes must be timezone-aware")
        return value.astimezone(UTC)


class GroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    username: str
    is_active: bool
    role: GroupRole
    joined_at: datetime

    @field_validator("joined_at")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("group member datetime must be timezone-aware")
        return value.astimezone(UTC)


class GroupDetailResponse(GroupResponse):
    members: list[GroupMemberResponse]


class GroupMemberCandidateResponse(BaseModel):
    user_id: UUID
    username: str


class GroupMemberCandidateListResponse(BaseModel):
    items: list[GroupMemberCandidateResponse]


class GroupListResponse(BaseModel):
    items: list[GroupResponse]
