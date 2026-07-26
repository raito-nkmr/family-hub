import re
import unicodedata
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.features.auth.models import SystemRole
from app.features.auth.passwords import MAXIMUM_PASSWORD_LENGTH, MINIMUM_PASSWORD_LENGTH

USERNAME_PATTERN = re.compile(r"^[\w.-]{1,64}$", re.UNICODE)


def normalize_username(value: str) -> str:
    username = unicodedata.normalize("NFKC", value).strip().casefold()
    if not USERNAME_PATTERN.fullmatch(username) or any(character.isspace() for character in username):
        raise ValueError("username must contain 1-64 letters, numbers, dots, underscores, or hyphens")
    return username


class LoginRequest(BaseModel):
    username: str
    password: str = Field(min_length=1, max_length=MAXIMUM_PASSWORD_LENGTH)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)


class UserResponse(BaseModel):
    id: UUID
    username: str
    system_role: SystemRole


class AdministrativeUserResponse(UserResponse):
    is_active: bool
    created_at: datetime
    active_session_count: int
    group_names: list[str]


class AdministrativeUserListResponse(BaseModel):
    items: list[AdministrativeUserResponse]


class AdministrativeUserStatusUpdate(BaseModel):
    is_active: bool
    current_password: str = Field(min_length=1, max_length=MAXIMUM_PASSWORD_LENGTH)


class AdministrativeUserRoleUpdate(BaseModel):
    system_role: SystemRole
    current_password: str = Field(min_length=1, max_length=MAXIMUM_PASSWORD_LENGTH)


class AdministrativeGroupHealthResponse(BaseModel):
    id: UUID
    name: str
    member_count: int
    active_admin_count: int
    updated_at: datetime


class AdministrativeGroupHealthListResponse(BaseModel):
    items: list[AdministrativeGroupHealthResponse]


class AdministrativeGroupAdministratorAssignment(BaseModel):
    user_id: UUID
    current_password: str = Field(min_length=1, max_length=MAXIMUM_PASSWORD_LENGTH)


class AdministrativeAuditEventResponse(BaseModel):
    id: UUID
    scope: str
    action: str
    actor_username: str
    group_id: UUID | None
    target_type: str
    target_id: str
    details: dict[str, object]
    created_at: datetime


class AdministrativeAuditEventListResponse(BaseModel):
    items: list[AdministrativeAuditEventResponse]


class AuthSessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAXIMUM_PASSWORD_LENGTH)
    new_password: str = Field(min_length=MINIMUM_PASSWORD_LENGTH, max_length=MAXIMUM_PASSWORD_LENGTH)


class UserSessionResponse(BaseModel):
    id: UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    current: bool


class UserSessionListResponse(BaseModel):
    items: list[UserSessionResponse]


class InvitationCreate(BaseModel):
    username: str
    expires_in_hours: int = Field(default=24, ge=1, le=168)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)


class InvitationAccept(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=MINIMUM_PASSWORD_LENGTH, max_length=MAXIMUM_PASSWORD_LENGTH)


class InvitationResponse(BaseModel):
    id: UUID
    username: str
    created_by_username: str
    created_at: datetime
    expires_at: datetime
    status: Literal["pending", "used", "expired", "revoked"]


class InvitationCreatedResponse(InvitationResponse):
    token: str


class InvitationListResponse(BaseModel):
    items: list[InvitationResponse]
