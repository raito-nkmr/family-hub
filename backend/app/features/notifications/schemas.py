from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

from app.features.notifications.models import NotificationType


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=512)
    auth: str = Field(min_length=10, max_length=256)


class PushSubscriptionCreate(BaseModel):
    endpoint: AnyHttpUrl
    keys: PushSubscriptionKeys
    locale: Literal["en", "ja"] = "en"

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("Push subscription endpoint must use HTTPS")
        if value.username or value.password or value.fragment or (value.port is not None and value.port != 443):
            raise ValueError("Push subscription endpoint contains unsupported URL components")
        return value


class PushSubscriptionLocaleUpdate(BaseModel):
    locale: Literal["en", "ja"]


class PushSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    locale: Literal["en", "ja"]


class NotificationPreferenceItem(BaseModel):
    notification_type: NotificationType
    enabled: bool


class NotificationPreferenceUpdate(BaseModel):
    items: list[NotificationPreferenceItem] = Field(min_length=3, max_length=3)


class NotificationConfigResponse(BaseModel):
    enabled: bool
    vapid_public_key: str | None
    subscription_ids: list[UUID]
    preferences: list[NotificationPreferenceItem]
